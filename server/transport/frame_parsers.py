"""
OpenAVC Frame Parsers — extract complete messages from a TCP/serial byte stream.

A FrameParser accumulates raw bytes via feed() and returns zero or more
complete messages when enough data has arrived. This decouples framing
logic from the transport layer.

Built-in parsers:
    - DelimiterFrameParser: splits on a byte sequence (e.g., \\r, \\r\\n)
    - LengthPrefixFrameParser: reads a length header then N bytes of payload
    - FixedLengthFrameParser: returns messages of exactly N bytes
    - CallableFrameParser: wraps a user function for custom protocols
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from server.utils.logger import get_logger

log = get_logger(__name__)

# Default max buffer size: 64 KB. Protects against unbounded growth from
# misbehaving devices or missing delimiters.
DEFAULT_MAX_BUFFER = 65536


class FrameParser(ABC):
    """Abstract base class for message frame parsers."""

    @abstractmethod
    def feed(self, data: bytes) -> list[bytes]:
        """
        Feed raw bytes into the parser.

        Returns a list of zero or more complete messages extracted from the
        internal buffer. Any incomplete trailing data is kept for the next
        feed() call.
        """

    @abstractmethod
    def reset(self) -> None:
        """Clear the internal buffer and any parser state."""


class DelimiterFrameParser(FrameParser):
    """
    Splits incoming bytes on a delimiter sequence.

    Messages are returned with the delimiter stripped.
    Empty messages (consecutive delimiters) are skipped.
    """

    def __init__(self, delimiter: bytes = b"\r", max_buffer: int = DEFAULT_MAX_BUFFER) -> None:
        if not delimiter:
            raise ValueError("Delimiter must not be empty")
        self._delimiter = delimiter
        self._buffer = b""
        self._max_buffer = max_buffer

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer += data
        messages: list[bytes] = []
        while self._delimiter in self._buffer:
            msg, self._buffer = self._buffer.split(self._delimiter, 1)
            if msg:  # Skip empty messages
                messages.append(msg)
        # Protect against unbounded growth (no delimiter arriving)
        if len(self._buffer) > self._max_buffer:
            log.warning(f"Delimiter parser buffer overflow ({len(self._buffer)} bytes), clearing")
            self._buffer = b""
        return messages

    def reset(self) -> None:
        self._buffer = b""


class LengthPrefixFrameParser(FrameParser):
    """
    Reads a fixed-size length header, then that many bytes of payload.

    The length header is big-endian unsigned int of ``header_size`` bytes
    (1, 2, or 4). An optional ``header_offset`` is added to the decoded
    length value (e.g., if the length field includes the header itself,
    set header_offset=-header_size).

    ``include_header`` controls whether the returned message includes the
    length header bytes or just the payload.
    """

    def __init__(
        self,
        header_size: int = 2,
        header_offset: int = 0,
        include_header: bool = False,
        max_buffer: int = DEFAULT_MAX_BUFFER,
    ) -> None:
        if header_size not in (1, 2, 4):
            raise ValueError("header_size must be 1, 2, or 4")
        self._header_size = header_size
        self._header_offset = header_offset
        self._include_header = include_header
        self._buffer = b""
        self._max_buffer = max_buffer

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer += data
        messages: list[bytes] = []
        while True:
            if len(self._buffer) < self._header_size:
                break
            # Decode length from header
            header = self._buffer[: self._header_size]
            payload_len = int.from_bytes(header, "big") + self._header_offset
            if payload_len < 0:
                payload_len = 0
            total = self._header_size + payload_len
            # A claimed frame larger than the whole buffer cap can never be
            # assembled — it's a desync or garbage. A length-prefixed stream
            # has no in-band resync point, so (like the sibling parsers on
            # overflow) clear the buffer instead of walking it one byte at a
            # time looking for a valid header — that byte-walk re-slices the
            # whole buffer each step (O(n^2)) on the shared event loop.
            if total > self._max_buffer:
                log.warning(
                    "Length-prefix parser: claimed frame size %d exceeds max "
                    "%d; clearing desynced buffer", total, self._max_buffer,
                )
                self._buffer = b""
                break
            if len(self._buffer) < total:
                break
            if self._include_header:
                messages.append(self._buffer[:total])
            else:
                messages.append(self._buffer[self._header_size : total])
            self._buffer = self._buffer[total:]
        # Defensive symmetry with the other parsers: never retain more than
        # max_buffer. A stalled partial frame (header received, payload never
        # completes) is otherwise silently pinned until disconnect.
        if len(self._buffer) > self._max_buffer:
            log.warning(
                "Length-prefix parser buffer overflow (%d bytes), clearing",
                len(self._buffer),
            )
            self._buffer = b""
        return messages

    def reset(self) -> None:
        self._buffer = b""


class FixedLengthFrameParser(FrameParser):
    """
    Returns messages of exactly ``length`` bytes.

    If the buffer contains fewer than ``length`` bytes, nothing is returned
    until enough data arrives.
    """

    def __init__(self, length: int, max_buffer: int = DEFAULT_MAX_BUFFER) -> None:
        if length <= 0:
            raise ValueError("length must be positive")
        self._length = length
        self._buffer = b""
        self._max_buffer = max_buffer

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer += data
        if len(self._buffer) > self._max_buffer:
            # Clear, don't trim. A fixed-length protocol has no in-band resync,
            # so keeping an arbitrary tail (max_buffer is rarely a multiple of
            # length) leaves every subsequent frame misaligned permanently.
            # Dropping to an empty buffer resyncs on the next whole frame.
            log.warning(
                "FixedLength parser buffer overflow (%d bytes), clearing",
                len(self._buffer),
            )
            self._buffer = b""
        messages: list[bytes] = []
        while len(self._buffer) >= self._length:
            messages.append(self._buffer[: self._length])
            self._buffer = self._buffer[self._length :]
        return messages

    def reset(self) -> None:
        self._buffer = b""


# SLIP (RFC 1055) control bytes. OSC 1.1 frames OSC packets over a byte
# stream (TCP/serial) with SLIP "double END" framing — each packet is
# wrapped END ... END. Used by QLab and other OSC-over-TCP show-control gear.
_SLIP_END = 0xC0
_SLIP_ESC = 0xDB
_SLIP_ESC_END = 0xDC
_SLIP_ESC_ESC = 0xDD


def slip_encode(payload: bytes) -> bytes:
    """Wrap a payload in a SLIP (RFC 1055) "double END" frame.

    The packet is emitted as ``END <escaped payload> END``. Inside the
    payload, a literal END byte is escaped to ESC ESC_END and a literal
    ESC byte to ESC ESC_ESC, so END never appears within the data and can
    safely delimit frames.
    """
    out = bytearray()
    out.append(_SLIP_END)
    for b in payload:
        if b == _SLIP_END:
            out.append(_SLIP_ESC)
            out.append(_SLIP_ESC_END)
        elif b == _SLIP_ESC:
            out.append(_SLIP_ESC)
            out.append(_SLIP_ESC_ESC)
        else:
            out.append(b)
    out.append(_SLIP_END)
    return bytes(out)


class SlipFrameParser(FrameParser):
    """
    Extracts SLIP (RFC 1055) framed messages from a byte stream.

    Frames are delimited by the END byte (0xC0). This handles both
    plain END-terminated SLIP and the "double END" variant QLab and the
    OSC 1.1 spec use (each packet wrapped END ... END) — the empty run
    between two consecutive END bytes simply yields no message.

    Because END never appears inside an escaped payload, splitting the
    buffer on raw END bytes is safe; each non-empty segment is then
    un-escaped (ESC ESC_END -> END, ESC ESC_ESC -> ESC). A trailing ESC
    with no following byte is kept in the buffer until the next feed().
    """

    def __init__(self, max_buffer: int = DEFAULT_MAX_BUFFER) -> None:
        self._buffer = bytearray()
        self._max_buffer = max_buffer

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer.extend(data)
        messages: list[bytes] = []

        while True:
            try:
                idx = self._buffer.index(_SLIP_END)
            except ValueError:
                break  # No complete frame terminator yet
            segment = bytes(self._buffer[:idx])
            del self._buffer[: idx + 1]
            if segment:  # Skip the empty run from double-END / leading END
                messages.append(_slip_unescape(segment))

        # Protect against unbounded growth (END never arriving). A SLIP
        # stream resyncs on the next END, so clearing (like the sibling
        # parsers) is the right recovery rather than walking byte-by-byte.
        if len(self._buffer) > self._max_buffer:
            log.warning(
                "SLIP parser buffer overflow (%d bytes), clearing",
                len(self._buffer),
            )
            self._buffer = bytearray()
        return messages

    def reset(self) -> None:
        self._buffer = bytearray()


def _slip_unescape(segment: bytes) -> bytes:
    """Reverse SLIP escaping within a single frame's payload."""
    if _SLIP_ESC not in segment:
        return segment  # Fast path — nothing escaped
    out = bytearray()
    escaped = False
    for b in segment:
        if escaped:
            if b == _SLIP_ESC_END:
                out.append(_SLIP_END)
            elif b == _SLIP_ESC_ESC:
                out.append(_SLIP_ESC)
            else:
                # Malformed escape — per RFC 1055 implementations are lenient;
                # keep the byte as-is rather than dropping data.
                out.append(b)
            escaped = False
        elif b == _SLIP_ESC:
            escaped = True
        else:
            out.append(b)
    return bytes(out)


class CallableFrameParser(FrameParser):
    """
    Wraps a user-supplied callable for custom framing logic.

    The callable signature is::

        def parse(buffer: bytes) -> tuple[bytes | None, bytes]

    It receives the current buffer and must return:
        - ``(message, remaining)`` if a complete message was found
        - ``(None, buffer)`` if more data is needed

    The parser calls the function repeatedly until it returns None,
    collecting all extracted messages.
    """

    def __init__(
        self,
        parse_fn: Callable[[bytes], tuple[bytes | None, bytes]],
        max_buffer: int = DEFAULT_MAX_BUFFER,
    ) -> None:
        self._parse_fn = parse_fn
        self._buffer = b""
        self._max_buffer = max_buffer

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer += data
        messages: list[bytes] = []
        try:
            while True:
                msg, remaining = self._parse_fn(self._buffer)
                if msg is None:
                    break
                messages.append(msg)
                if len(remaining) >= len(self._buffer):
                    # No forward progress: a buggy parse_fn returned a message
                    # without consuming any buffer. Without this guard the loop
                    # spins forever and wedges the shared event loop (every
                    # device, poll, and WS client). Take the message it found,
                    # then stop this pass.
                    log.warning(
                        "Custom frame parser made no forward progress "
                        "(buffer not consumed); stopping to avoid a hang"
                    )
                    self._buffer = remaining
                    break
                self._buffer = remaining
        except Exception:  # Catch-all: user-supplied parse_fn can raise anything
            log.exception("Error in custom frame parser function, clearing buffer")
            self._buffer = b""
        # Protect against unbounded growth
        if len(self._buffer) > self._max_buffer:
            log.warning(f"Callable parser buffer overflow ({len(self._buffer)} bytes), clearing")
            self._buffer = b""
        return messages

    def reset(self) -> None:
        self._buffer = b""
