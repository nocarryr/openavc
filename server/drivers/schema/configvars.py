from __future__ import annotations
from typing import (
    Generic, Literal, TypedDict, NotRequired, Sequence, Any, TYPE_CHECKING,
)

from .types import (
    ConfigVarType, ConfigVarPyType, NumericT, StateVarType, _SchemaVarScalarT,
    DeviceSettingType, DeviceSettingPyType,
)
if TYPE_CHECKING:
    from .commands import CommandItemSerialTCP, CommandItemHTTP

__all__ = [
    "AnyConfigVar",
    "AnyStateVar",
    "AnyDeviceSetting",
    "DeviceSetting",
    "DeviceSettingScalar",
    "DeviceSettingEnum",
]


class _ConfigVar(TypedDict, Generic[ConfigVarType, ConfigVarPyType]):
    """Base class for configuration variables."""
    type: ConfigVarType
    """Type of the configuration variable.
    Can be one of 'string', 'integer', 'number', 'float', 'boolean', 'enum' or 'object'.
    """
    label: str
    """Human-readable label for the configuration variable."""
    required: NotRequired[bool]
    """Indicates whether the configuration variable is required."""
    default: NotRequired[ConfigVarPyType]
    """Default value for the configuration variable."""
    description: NotRequired[str]
    """Optional description for the configuration variable."""


class ConfigVarString(_ConfigVar[Literal["string", "text"], str]):
    """Configuration variable for string type."""
    pass

class ConfigVarBoolean(_ConfigVar[Literal["boolean"], bool]):
    """Configuration variable for boolean type."""
    pass


class ConfigVarNumeric(_ConfigVar[Literal["integer", "number", "float"], NumericT]):
    """Configuration variable for numeric types (integer, number, float)."""
    min: NotRequired[NumericT]
    """Minimum value for the numeric configuration variable."""
    max: NotRequired[NumericT]
    """Maximum value for the numeric configuration variable."""


class ConfigVarObject(_ConfigVar[Literal["object"], dict[str, Any]]):
    """Configuration variable for object type."""
    pass


class ConfigVarEnum(_ConfigVar[Literal["enum"], str]):
    """Configuration variable for enum type."""
    values: list[str]
    """List of possible values for the enum configuration variable."""


AnyConfigVar = ConfigVarString | ConfigVarBoolean | ConfigVarNumeric | ConfigVarObject | ConfigVarEnum
"""Type alias for any configuration variable."""


class _StateVar(TypedDict, Generic[StateVarType]):
    """Base class for state variables."""
    type: StateVarType
    """Type of the state variable.
    Can be one of 'string', 'integer', 'number', 'float', 'boolean', or 'enum'.
    """
    label: str
    """Human-readable label for the state variable."""
    help: NotRequired[str]
    """Optional help text for the state variable."""


class ScalarStateVar(_StateVar[_SchemaVarScalarT]):
    """State variable for scalar types (string, integer, number, float, boolean)."""
    pass


class EnumStateVar(_StateVar[Literal["enum"]]):
    """State variable for enum type."""
    values: list[str]
    """List of possible values for the enum state variable."""

AnyStateVar = ScalarStateVar | EnumStateVar
"""Type alias for any state variable."""



class DeviceSetting(TypedDict, Generic[DeviceSettingType, DeviceSettingPyType]):
    """Schema for a device setting, which is a configuration variable
    with an associated write command.
    """
    type: DeviceSettingType
    """Type of the device setting.
    Can be one of 'string', 'integer', 'number', 'float', 'boolean', or 'enum'.
    """
    label: str
    """Human-readable label for the device setting."""
    help: NotRequired[str]
    """Optional help text for the device setting."""
    default: NotRequired[DeviceSettingPyType]
    """Default value for the device setting."""
    state_key: str
    """The state variable key that reflects the current value of this setting."""
    setup: bool
    """Indicates whether to show this setting in the Add Device dialog."""
    unique: NotRequired[bool]
    """Indicates whether to auto-generate a non-clashing default value for this setting."""
    regex: NotRequired[str]
    """Optional regex pattern to validate the value of this setting."""
    write: NotRequired[CommandItemSerialTCP | CommandItemHTTP]
    """Command to send to the device to update this setting when changed by the user."""


class DeviceSettingScalar(DeviceSetting[Literal["string", "integer", "number", "float", "boolean"], DeviceSettingPyType]):
    """Device setting for scalar types (string, integer, number, float, boolean)."""
    min: NotRequired[DeviceSettingPyType]
    """Minimum value for the device setting (applicable for numeric types)."""
    max: NotRequired[DeviceSettingPyType]
    """Maximum value for the device setting (applicable for numeric types)."""


class DeviceSettingEnum(DeviceSetting[Literal["enum"], str]):
    """Device setting for enum type."""
    values: Sequence[str]
    """List of possible values for the enum device setting."""

AnyDeviceSetting = DeviceSettingScalar | DeviceSettingEnum
"""Type alias for any device setting."""
