"""Plugin CONFIG_SCHEMA validation, shared by every config-write path.

The REST endpoint (server/api/plugins.py) and the cloud AI tool
(server/cloud/tools/plugin_tools.py) both persist plugin config; they must
accept and reject exactly the same shapes, so the validator lives here and
both import it.
"""

from typing import Any

SCHEMA_TYPE_VALIDATORS: dict[str, type | tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
}


def validate_plugin_config(config: dict, schema: dict) -> str | None:
    """Validate plugin config against its CONFIG_SCHEMA.

    Returns error string or None. Only checks required fields and basic types.
    """
    errors: list[str] = []
    for key, field_def in schema.items():
        if not isinstance(field_def, dict):
            continue

        # Group fields — recurse
        if field_def.get("type") == "group":
            sub_schema = field_def.get("fields", {})
            sub_config = config.get(key, {})
            if isinstance(sub_schema, dict) and isinstance(sub_config, dict):
                err = validate_plugin_config(sub_config, sub_schema)
                if err:
                    errors.append(err)
            continue

        # Required field check
        if field_def.get("required") and key not in config:
            if "default" not in field_def:
                errors.append(f"Missing required config field '{key}'")
                continue

        # Type check for present values
        value = config.get(key)
        if value is not None:
            expected_type = field_def.get("type", "")
            valid_types = SCHEMA_TYPE_VALIDATORS.get(expected_type)
            if valid_types and not isinstance(value, valid_types):
                errors.append(
                    f"Config field '{key}' should be {expected_type}, "
                    f"got {type(value).__name__}"
                )

    if errors:
        return "Plugin config validation failed: " + "; ".join(errors)
    return None


def validate_config_for_plugin(plugin_id: str, config: dict) -> str | None:
    """Validate config against the installed plugin's CONFIG_SCHEMA.

    Returns error string or None. A plugin that isn't installed (or has no
    schema) validates clean — config for missing plugins is stored as-is so
    it survives until the plugin is installed.
    """
    from server.core.plugin_loader import _PLUGIN_CLASS_REGISTRY

    plugin_class = _PLUGIN_CLASS_REGISTRY.get(plugin_id)
    if plugin_class is None:
        return None
    schema: Any = getattr(plugin_class, "CONFIG_SCHEMA", None)
    if not schema or not isinstance(schema, dict):
        return None
    return validate_plugin_config(config, schema)
