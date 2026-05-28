from __future__ import annotations
from typing import (
    TypeVar, Generic, Literal, TypedDict, NotRequired, Sequence, Mapping, TYPE_CHECKING,
)


if TYPE_CHECKING:
    from .configvars import AnyStateVar

__all__ = [
    "ChildEntityIdFormat",
    "ChildEntityItem",
    "AuthSchema",
    "AnyFrameParser",
    "PollingSchema",
]


# -------- Child Entity schemas --------

class ChildEntityIdFormat(TypedDict):
    """Schema for child entity ID format."""
    type: Literal["integer"]
    """Format for child entity IDs. Currently only supports 'integer' type."""
    min: NotRequired[int]
    """Minimum value for the child entity ID. Default is 1 if not specified."""
    max: NotRequired[int]
    """Maximum value for the child entity ID. Unbounded if not specified."""
    pad_width: int
    """Zero-pads the ID in state keys (0 = no padding)."""


class ChildEntityItem(TypedDict):
    """Schema for a child entity item."""
    label: str
    """Human-readable label for the child entity."""
    label_plural: str
    """Human-readable plural label for the child entity."""
    id_format: ChildEntityIdFormat
    """Format for the child entity IDs."""
    state_variables: Mapping[str, AnyStateVar]
    """Mapping of state variable names to their schemas for the child entity."""
    summary_fields: Sequence[str]
    """Optional list of state variable names to include in the summary for the child entity.

    This lists which fields appear as columns in the list view; ``label_field``
    names the field carrying the controller's own name for the unit
    (the user-set label is separate and lives in the project file).
    """



# -------- Authentication schema --------

class AuthSchema(TypedDict):
    """Schema for authentication configuration."""
    type: Literal["telnet_login"]
    """Type of authentication method. Currently only supports 'telnet_login'."""
    username_prompt: str
    """Regex pattern to match the username prompt from the device."""
    password_prompt: str
    """Regex pattern to match the password prompt from the device."""
    success_pattern: NotRequired[str]
    """Optional regex pattern to match a successful login prompt from the device.

    If omitted, any response that doesn't match the failure pattern is considered a successful login.
    """
    failure_pattern: NotRequired[str]
    """Optional regex pattern to match a failed login response from the device.

    If matched, the login attempt is considered failed immediately.
    """
    username_field: NotRequired[str]
    """Optional configuration field name that holds the username.
    Defaults to 'username'.
    """
    password_field: NotRequired[str]
    """Optional configuration field name that holds the password.
    Defaults to 'password'.
    """
    skip_if_empty: NotRequired[bool]
    """If true and the username field is blank, the authentication handshake is skipped.
    Defaults to true.
    """
    timeout_seconds: NotRequired[int]
    """Number of seconds to wait for each prompt during the authentication
    handshake before timing out. Defaults to 10 seconds.
    """
    line_ending: NotRequired[str]
    """Line ending to append after sending the username and password.
    Defaults to '\\r\\n'.
    """


# ------- Frame parser schemas --------

FrameParserType = TypeVar("FrameParserType", bound=Literal["length_prefix", "fixed_length"])
"""Type variable for frame parser types."""

class FrameParserBase(TypedDict, Generic[FrameParserType]):
    """Base class for frame parsers."""
    type: FrameParserType
    """Type of frame parser. Can be either 'length_prefix' or 'fixed_length'."""

class FrameParserLengthPrefix(FrameParserBase[Literal["length_prefix"]]):
    """Schema for a length prefix frame parser."""
    header_size: Literal[1, 2, 4]
    """Number of bytes used for the length header (1, 2, or 4)."""
    header_offset: int
    """Offset added to the decoded length value."""
    include_header: bool
    """Indicates whether to include the length header in the returned message."""


class FrameParserFixedLength(FrameParserBase[Literal["fixed_length"]]):
    """Schema for a fixed length frame parser."""
    length: int
    """Exact message length in bytes."""

AnyFrameParser = FrameParserLengthPrefix | FrameParserFixedLength
"""Type alias for any frame parser."""



# -------- Polling schema --------

class PollingSchema(TypedDict):
    """Schema for polling configuration."""
    queries: Sequence[str]
    """Sequence of commands to send for polling the device state."""
