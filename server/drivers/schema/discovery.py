from __future__ import annotations
from typing import (
    Union, TypedDict, NotRequired, Mapping, Sequence,
)

__all__ = [
    "MDNSFingerprint",
    "AMXDDPFingerprint",
    "ProbeExtractionRule",
    "TCPUDPProbe",
    "DiscoveryHints",
    "PythonDiscovery",
    "DiscoveryFingerprint",
    "DiscoverySchema",
]


class MDNSFingerprint(TypedDict):
    """Either a simple service string or a structured declaration with a TXT-record filter.
    """
    service: str
    """Service string for mDNS discovery (e.g., "_http._tcp.local.")."""
    txt: NotRequired[Mapping[str, str]]
    """Optional TXT-record filter for mDNS discovery.
    All key-value pairs must match for the fingerprint to match.
    Example: {"manufacturer": "Shure"}.
    """


class AMXDDPFingerprint(TypedDict):
    """Structured declaration for AMX DDP discovery."""
    make: str
    """Device make for AMX DDP discovery (e.g., "Polycom")."""
    model_pattern: NotRequired[str]
    """Optional model pattern for AMX DDP discovery.
    This is a glob-style pattern (e.g., ``"SoundStructure*"``) that matches
    the device model. If omitted, it defaults to "*", matching all models.
    """


class ProbeExtractionRule(TypedDict):
    """Structured declaration for metadata extraction from probe responses."""
    regex: str
    """Regex pattern to apply to the probe response for extracting metadata."""
    group: int
    """Regex group number to extract as the metadata value."""


class TCPUDPProbe(TypedDict):
    """Structured declaration for TCP or UDP probe discovery."""
    port: int
    """TCP or UDP port to probe."""
    send_ascii: NotRequired[str]
    """ASCII string to send for the probe. If omitted, the probe performs a
    connect-only banner read.

    Only one of :attr:`send_ascii` or :attr:`send_hex` should be provided.
    """
    send_hex: NotRequired[str]
    """Hex string to send for the probe. If omitted, the probe performs a
    connect-only banner read.

    Only one of :attr:`send_ascii` or :attr:`send_hex` should be provided.
    """
    expect: NotRequired[str]
    """Expected response for the probe. This can be a simple substring match,
    a regex pattern, or a hex string.

    Only one of :attr:`expect`, :attr:`expect_regex`, or :attr:`expect_hex`
    should be provided.
    """
    expect_regex: NotRequired[str]
    """Expected response for the probe as a regex pattern.

    Only one of :attr:`expect`, :attr:`expect_regex`, or :attr:`expect_hex`
    should be provided.
    """
    expect_hex: NotRequired[str]
    """Expected response for the probe as a hex string.

    Only one of :attr:`expect`, :attr:`expect_regex`, or :attr:`expect_hex`
    should be provided.
    """
    cross_vendor: bool
    """Whether this probe identifies a cross-vendor protocol class rather than a specific vendor.

    If true, the matcher checks peer drivers' hints against the same device's
    evidence to potentially demote this driver to an alternative if a better
    match is found.
    Default is false.
    """
    extract_manufacturer: NotRequired[str]
    """Optional manufacturer string to extract from the probe response.
    This feeds into the :attr:`~DiscoveryHints.manufacturer_alias` hint path,
    allowing the matcher to pick a vendor-specific peer when this driver carries
    :attr:`cross_vendor` set to true.
    """
    extract: NotRequired[Mapping[str, ProbeExtractionRule]]  # optional — free-form metadata
    """Optional free-form metadata extraction rules. Each key is a metadata field name,
    and the value is a :class:`ProbeExtractionRule` that defines how to extract
    that metadata from the probe response using regex patterns.
    """
    timeout_ms: NotRequired[int]
    """Optional timeout for the probe in milliseconds. Default is 3000 ms.
    The maximum allowed value is 10000 ms to prevent a slow probe from stretching the scan budget.
    """


class DiscoveryHints(TypedDict):
    """Structured declaration for discovery hints that narrow candidate drivers."""
    oui: NotRequired[Sequence[str]]
    """Optional list of OUI prefixes for MAC address matching
    (e.g., ["00:0e:dd", "d8:34:ee"]).
    """
    hostname: NotRequired[Sequence[str]]
    """Optional list of regex patterns for hostname matching."""
    port_open: NotRequired[Sequence[int]]
    """Optional list of vendor-specific TCP ports for matching."""
    manufacturer_alias: NotRequired[Sequence[str]]
    """Optional list of manufacturer aliases for case-insensitive exact matching."""
    snmp_pen: NotRequired[int]
    """Optional IANA Private Enterprise Number for SNMP matching."""


class PythonDiscovery(TypedDict):
    """Structured declaration for Python-based discovery."""
    file: str
    """Path to the Python discovery module, relative to the driver YAML file."""
    cross_vendor: bool
    """Whether this Python discovery identifies a cross-vendor protocol class rather than a specific vendor.

    If true, the matcher checks peer drivers' hints against the same device's
    evidence to potentially demote this driver to an alternative if a better
    match is found.
    Default is false.
    """

class DiscoveryFingerprint(TypedDict):
    """Structured declaration for discovery fingerprints that identify the driver."""
    mdns: NotRequired[str | Sequence[str | MDNSFingerprint]]
    """Optional mDNS service string(s) or structured declarations for discovery.
    This can be a simple service string (e.g., "_pjlink._tcp.local.") or a list
    of service strings and/or :class:`MDNSFingerprint` mappings.
    """
    ssdp: NotRequired[str | Sequence[str]]
    """Optional SSDP service string(s) for discovery
    (e.g., "urn:schemas-upnp-org:device:MediaRenderer:1").

    This can be a single string or a list of strings.
    """
    amx_ddp: NotRequired[AMXDDPFingerprint]
    """Optional structured declaration for AMX DDP discovery."""
    tcp_probe: NotRequired[TCPUDPProbe]
    """Optional structured declaration for TCP probe discovery."""
    udp_probe: NotRequired[TCPUDPProbe]
    """Optional structured declaration for UDP probe discovery."""
    python: NotRequired[PythonDiscovery]
    """Optional structured declaration for Python-based discovery."""


DiscoverySchema = Union[DiscoveryFingerprint, DiscoveryHints]
"""Schema for the `discovery` key in the driver schema definition."""
