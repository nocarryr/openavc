"""
Schema definitions for drivers

This module defines the schema for drivers, which includes:

- Configuration variables (config vars) that specify how to connect to and configure a device.
- State variables that represent the current state of the device.
- Commands that can be sent to the device, along with their parameters and expected responses.
- Metadata about the driver, such as its name, manufacturer, supported models, and help text.


It was built from the description found in the OpenAVC driver development documentation
found at https://github.com/open-avc/openavc-drivers/blob/main/AGENTS.md

Permalink:
https://github.com/open-avc/openavc-drivers/blob/5b3b356eec3ce1791c4a6442119c9f3ff76203c5/AGENTS.md
"""
from __future__ import annotations
from typing import (
    Literal, TypedDict, NotRequired, Mapping, Sequence, Any,
)


from .configvars import (
    AnyConfigVar,
    AnyStateVar,
    AnyDeviceSetting,
    ConfigVarString,
    ConfigVarBoolean,
    ConfigVarNumeric,
    ConfigVarEnum,
)
from .commands import (
    AnyCommandParam,
    CommandParamString,
    CommandParamBoolean,
    CommandParamNumeric,
    CommandParamEnum,
    CommandItemSerialTCP,
    CommandItemHTTP,
    CommandItem,
    CommandResponseItem,
    CommandResponseShorthandItem,
    CommandResponseVerboseItem,
    CommandResponseMappingItem,
)

from .misc import (
    ChildEntityItem,
    AuthSchema,
    AnyFrameParser,
    PollingSchema,
)
from .discovery import DiscoverySchema

__all__ = [
    "AnyConfigVar",
    "AnyStateVar",
    "AnyDeviceSetting",
    "ConfigVarString",
    "ConfigVarBoolean",
    "ConfigVarNumeric",
    "ConfigVarEnum",
    "AnyCommandParam",
    "CommandParamString",
    "CommandParamBoolean",
    "CommandParamNumeric",
    "CommandParamEnum",
    "CommandItemSerialTCP",
    "CommandItemHTTP",
    "CommandItem",
    "CommandResponseItem",
    "CommandResponseShorthandItem",
    "CommandResponseVerboseItem",
    "CommandResponseMappingItem",
    "ChildEntityItem",
    "AuthSchema",
    "AnyFrameParser",
    "PollingSchema",
    "DiscoverySchema",
    "DriverMetadata",
    "DriverSchema",
]

TransportType = Literal["tcp", "serial", "http", "udp", "osc"]
"""Type alias for transport types."""

DriverCategory = Literal[
    "projector", "display", "switcher", "scaler", "audio", "camera", "lighting",
    "relay", "utility", "other",
]
"""Type alias for driver categories."""




class CompatibleModelEntry(TypedDict):
    """Schema for a :attr:`~DriverMetadata.compatible_models` entry in
    :class:`DriverMetadata`.
    """
    manufacturer: str
    """Manufacturer name. Must match an entry in manufacturers.json."""
    models: Sequence[str]
    """List of compatible model names from this manufacturer."""
    confidence: Literal["full", "partial", "untested"]
    """Confidence level for compatibility with these models."""
    notes: NotRequired[str]
    """Optional notes about compatibility with these models."""


class DriverMetadataHelp(TypedDict):
    """Schema for the :attr:`~DriverMetadata.help` field in :class:`DriverMetadata`.
    """
    overview: str
    """Overview text for the driver, shown in the Add Device dialog."""
    setup: str
    """Setup instructions for the driver, shown in the Add Device dialog."""


class DriverMetadata(TypedDict):
    """Schema for driver metadata."""
    id: str
    """Unique identifier for the driver. Lowercase, underscores only (e.g., `extron_sis`)."""
    name: str
    """Human-readable display name for the driver."""
    manufacturer: str
    """Manufacturer name. Must appear in manufacturers.json."""
    category: DriverCategory
    """Category for the driver. Used for grouping in the UI."""
    version: str
    """Semantic version of the driver (e.g., `1.0.0`). Bump on every change."""
    author: str
    """Driver author. Your name or GitHub handle."""
    description: str
    """Brief description of the driver for AV integrators.
    Plain language, no marketing fluff.
    """
    source_url: str
    """URL to the protocol document or canonical implementation you built from.
    No driver ships without this.
    """
    ports: NotRequired[Sequence[int]]
    """Default network ports the device listens on (1-65535)."""
    protocols: NotRequired[Sequence[str]]
    """Protocol family identifiers (e.g., `["pjlink"]`)."""
    simulated: NotRequired[bool]
    """True if a simulator covers this driver."""
    verified: NotRequired[bool]
    """True only after testing on real hardware."""
    min_platform_version: NotRequired[str]
    """Minimum OpenAVC version (semver).
    Omit when compatible with all platform versions.
    """
    tags: NotRequired[Sequence[str]]
    """Lowercase, hyphen-separated keywords for Browse Drivers search.
    Examples: `["ndi", "ptz"]`, `["ceiling-mic"]`.
    """
    help: NotRequired[DriverMetadataHelp]
    """Help text for the driver, shown in the Add Device dialog.
    Can include 'overview' and 'setup' keys.
    """
    deprecated: NotRequired[bool]
    """Mark superseded drivers."""
    replacement_id: NotRequired[str]
    """Required when :attr:`deprecated` is True. Must reference another driver's `id`.
    """
    compatible_models: NotRequired[Sequence[CompatibleModelEntry]]
    """List of compatible models for this driver."""



class DriverSchema(DriverMetadata):
    """Schema for a driver."""
    transport: TransportType
    """Transport type for the driver.
    Can be one of: 'tcp', 'serial', 'http', 'udp', 'osc'.
    """
    discovery: NotRequired[DiscoverySchema]
    """Optional network discovery schema for the driver."""
    default_config: Mapping[str, Any]
    """Default values for device connection settings. These pre-fill the Add Device dialog.

    .. todo::

        Type the values in this mapping based on the declared config_schema
        (if possible given Python's type system limitations) and validate them
        against the config_schema.

    """
    config_schema: Mapping[str, AnyConfigVar]
    """Mapping of configuration variable names to their schemas."""
    state_variables: Mapping[str, AnyStateVar]
    """Mapping of state variable names to their schemas."""
    child_entity_types: NotRequired[Mapping[str, ChildEntityItem]]
    """Optional mapping of child entity type names to their schemas."""
    commands: Mapping[str, CommandItem]
    """Mapping of command names to their schemas."""
    responses: NotRequired[Sequence[CommandResponseItem]]
    """Optional sequence of command response items for parsing command responses."""
    auth: NotRequired[AuthSchema]
    """Optional authentication schema for drivers that require authentication."""
    on_connect: NotRequired[Sequence[str]]
    """Commands sent once immediately after connection
    (and after the auth: handshake completes, if any), before polling starts.
    Use for enabling feedback/verbose mode or requesting initial state.
    """
    polling: NotRequired[PollingSchema]
    """Periodic status queries sent to the device. The poll cadence is set by
    `default_config.poll_interval` (and overridden per-device by the project's
    `config.poll_interval`) — `polling:` only declares the queries to run.
    """
    device_settings: NotRequired[Mapping[str, AnyDeviceSetting]]
    """Configurable values that live on the device hardware (not in the project file).

    These are writable and polled. The system queues writes for offline devices
    and sends them when the device reconnects.
    """
    frame_parser: NotRequired[AnyFrameParser]
    """Optional frame parser configuration for serial/TCP drivers that require custom framing."""
