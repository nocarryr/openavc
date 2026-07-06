"""
OpenAVC log buffer — captures Python logging output for streaming.

Provides a circular buffer that captures all log records and makes them
available via subscribe/unsubscribe for real-time WebSocket streaming,
plus a get_recent() method for REST access.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class LogEntry:
    """A single captured log entry."""
    timestamp: float
    level: str
    source: str
    category: str  # "system", "device", "script", "macro"
    message: str
    device: str = ""  # device id for device-category entries, "" otherwise

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Drivers, transports, and BaseDriver all prefix their log lines with
# "[<device_id>] " — the one place a device id reliably appears in a record.
_DEVICE_PREFIX = re.compile(r"^\[([^\]\s]+)\]")


def _extract_device(category: str, message: str) -> str:
    if category != "device":
        return ""
    m = _DEVICE_PREFIX.match(message)
    return m.group(1) if m else ""


def _categorize_source(name: str, message: str) -> str:
    """Derive a category from the logger name and message content."""
    if name.startswith("server.core.macro_engine"):
        return "macro"
    if (
        name.startswith("server.drivers")
        or name.startswith("server.core.device_manager")
        or name.startswith("server.transport")
    ):
        return "device"
    if name.startswith("openavc") or name.startswith("server.core.script"):
        return "script"
    return "system"


class LogBuffer:
    """Thread-safe circular buffer for log entries with pub/sub support."""

    def __init__(self, maxlen: int = 500):
        self._entries: deque[LogEntry] = deque(maxlen=maxlen)
        self._subscribers: dict[str, asyncio.Queue[LogEntry]] = {}

    def append(self, entry: LogEntry) -> None:
        """Add an entry and push to all subscribers."""
        self._entries.append(entry)
        for queue in self._subscribers.values():
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                # Drop oldest if subscriber is slow
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(entry)
                except asyncio.QueueFull:
                    pass

    def subscribe(self) -> tuple[str, asyncio.Queue[LogEntry]]:
        """Create a new subscription. Returns (sub_id, queue)."""
        sub_id = str(uuid.uuid4())
        queue: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=200)
        self._subscribers[sub_id] = queue
        return sub_id, queue

    def unsubscribe(self, sub_id: str) -> None:
        """Remove a subscription."""
        self._subscribers.pop(sub_id, None)

    def get_recent(self, count: int = 100) -> list[dict[str, Any]]:
        """Get the ``count`` most recent entries as dicts.

        A count of 0 (or negative) returns an empty list — the ``[-count:]``
        slice would otherwise turn 0 into the whole buffer and a negative
        count into a wrong window (same trap as StateStore.get_history).
        """
        if count <= 0:
            return []
        entries = list(self._entries)
        if count < len(entries):
            entries = entries[-count:]
        return [e.to_dict() for e in entries]


class BufferHandler(logging.Handler):
    """Logging handler that feeds records into a LogBuffer."""

    def __init__(self, buffer: LogBuffer):
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record) if self.formatter else record.getMessage()
            category = _categorize_source(record.name, message)
            entry = LogEntry(
                timestamp=time.time(),
                level=record.levelname,
                source=record.name,
                category=category,
                message=message,
                device=_extract_device(category, record.getMessage()),
            )
            self._buffer.append(entry)
        except Exception:
            # Catch-all: follows logging.Handler convention — emit() must never propagate
            self.handleError(record)


# Singleton
_log_buffer: LogBuffer | None = None


def get_log_buffer() -> LogBuffer:
    """Get or create the global LogBuffer singleton."""
    global _log_buffer
    if _log_buffer is None:
        _log_buffer = LogBuffer()
    return _log_buffer
