from __future__ import annotations
from typing import (
    Generic, Literal, TypedDict, NotRequired, Mapping, Sequence,
)

from .types import (
    CommandParamType, CommandParamPyType, _SchemaVarScalarT, NumericT,
)

__all__ = [
    "AnyCommandParam",
    "CommandParamString",
    "CommandParamBoolean",
    "CommandParamNumeric",
    "CommandParamEnum",
    "CommandItem",
    "CommandResponseItem",
    "CommandResponseShorthandItem",
    "CommandResponseVerboseItem",
]


class _CommandParam(TypedDict, Generic[CommandParamType, CommandParamPyType]):
    type: CommandParamType
    """Type of the command parameter.
    Can be one of 'string', 'integer', 'number', 'float', 'boolean', or 'enum'.
    """
    label: str
    """Human-readable label for the command parameter."""
    required: NotRequired[bool]
    """Indicates whether the command parameter is required."""
    help: NotRequired[str]
    """Optional help text for the command parameter."""


class CommandParamString(_CommandParam[Literal["string"], str]):
    """Command parameter for string type."""
    pass


class CommandParamBoolean(_CommandParam[Literal["boolean"], bool]):
    """Command parameter for boolean type."""
    pass


class CommandParamNumeric(_CommandParam[_SchemaVarScalarT, NumericT]):
    """Command parameter for numeric types (integer, number, float)."""
    min: NotRequired[NumericT]
    """Minimum value for the numeric command parameter."""
    max: NotRequired[NumericT]
    """Maximum value for the numeric command parameter."""


class CommandParamEnum(_CommandParam[Literal["enum"], str]):
    """Command parameter for enum type."""
    values: list[str]
    """List of possible values for the enum command parameter."""


AnyCommandParam = CommandParamString | CommandParamBoolean | CommandParamNumeric | CommandParamEnum
"""Type alias for any command parameter."""

CommandMethodType = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
"""HTTP methods that can be used for commands."""


class CommandItemBase(TypedDict):
    """Base class for command items."""
    label: str
    """Human-readable label for the command."""
    params: NotRequired[Mapping[str, AnyCommandParam]]
    """Mapping of parameter names to their schemas."""
    help: NotRequired[str]
    """Optional help text for the command."""


class CommandItemSerialTCP(CommandItemBase):
    """Schema for a command item that is sent over serial or TCP."""
    send: NotRequired[str]
    """String to send for the command (e.g., over serial or TCP)."""


class CommandItemHTTP(CommandItemBase):
    """Schema for a command item."""

    method: NotRequired[CommandMethodType]
    """HTTP method to use for the command."""
    path: NotRequired[str]
    """URL path for the command."""
    body: NotRequired[str]
    """Optional body for the command (e.g., JSON strings)."""


CommandItem = CommandItemSerialTCP | CommandItemHTTP
"""Schema for a command item, which can be either a serial/TCP command or an HTTP command."""


CommandResponseShorthandItem = TypedDict("CommandResponseShorthandItem", {
    "match": str,
    "set": NotRequired[Mapping[str, str]],
})
"""Schema for a command response item in shorthand form (without 'type' field)."""

class CommandResponseMappingItem(TypedDict):
    """Schema for a command response mapping item."""
    group: int
    """The capture group number from the regex match to use for this mapping."""
    state: str
    """The state variable to update with the value from the capture group."""
    type: NotRequired[_SchemaVarScalarT]
    """Optional type of the value to set for the state variable.
    Can be one of 'string', 'integer', 'number', 'float', or 'boolean'.
    """
    map: NotRequired[Mapping[str, str]]
    """Optional mapping of raw values to mapped values for the state variable."""


CommandResponseVerboseItem = TypedDict("CommandResponseVerboseItem", {
    "match": str,
    "mappings": Sequence[CommandResponseMappingItem],
})
"""Schema for a command response item in verbose form (with 'type' field and support for multiple mappings)."""

CommandResponseItem = CommandResponseShorthandItem | CommandResponseVerboseItem
"""Schema for a command response item, which can be in either shorthand or verbose form."""
