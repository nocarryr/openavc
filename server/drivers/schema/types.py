from __future__ import annotations
from typing import (
    TypeVar, Literal, Any,
)


_SchemaVarScalarT = Literal["string", "integer", "number", "float", "boolean"]
"""Schema variable types that are not enums."""

NumericT = TypeVar("NumericT", int, float)
"""Type variable for numeric types (integer, number, float)."""

_SchemaConfigVarT = _SchemaVarScalarT | Literal["enum", "text", "object"]
"""All configuration variable types."""
ConfigVarType = TypeVar("ConfigVarType", bound=_SchemaConfigVarT)
"""Type variable for configuration variable types."""
ConfigVarPyType = TypeVar("ConfigVarPyType", str, int, float, bool, list[str], dict[str, Any])
"""Type variable for Python types corresponding to configuration variable types."""


_SchemaDeviceSettingT = _SchemaVarScalarT | Literal["enum"]
"""All device setting types."""
DeviceSettingType = TypeVar("DeviceSettingType", bound=_SchemaDeviceSettingT)
"""Type variable for device setting types."""
DeviceSettingPyType = TypeVar("DeviceSettingPyType", str, int, float, bool)
"""Type variable for Python types corresponding to device setting types."""


_StateVarT = _SchemaVarScalarT | Literal["enum"]
"""All state variable types."""
StateVarType = TypeVar("StateVarType", bound=_StateVarT)
"""Type variable for state variable types."""
StateVarPyType = TypeVar("StateVarPyType", str, int, float, bool)
"""Type variable for Python types corresponding to state variable types."""


_CommandParamT = _SchemaVarScalarT | Literal["enum"]
"""All command parameter types."""
CommandParamType = TypeVar("CommandParamType", bound=_CommandParamT)
"""Type variable for command parameter types."""
CommandParamPyType = TypeVar("CommandParamPyType", str, int, float, bool)
"""Type variable for Python types corresponding to command parameter types."""
