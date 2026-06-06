"""
OpenAVC Generic TCP Driver.

A utility driver for controlling any TCP device by sending raw commands.
Commands are defined in the device config and can include parameter substitution.

Useful for devices without a dedicated driver — the integrator defines the
command strings directly in the project configuration.
"""

from __future__ import annotations

import json
import re
from typing import Any

from server.drivers.base import BaseDriver
from server.transport.binary_helpers import encode_escape_sequences
from server.utils.logger import get_logger

log = get_logger(__name__)


class GenericTCPDriver(BaseDriver):
    """Generic TCP device driver with configurable commands.

    Connection / disconnection are inherited from ``BaseDriver`` (the
    ``transport: tcp`` auto-transport path) so this driver gets the shared
    close-before-reconnect, control-interface binding, port coercion, and
    disconnect cleanup instead of a hand-rolled fork of them. The only
    device-specific behavior is the configurable command map and the
    raw-response event.
    """

    DRIVER_INFO = {
        "id": "generic_tcp",
        "name": "Generic TCP Device",
        "manufacturer": "Generic",
        "category": "utility",
        "version": "1.0.0",
        "author": "OpenAVC",
        "description": (
            "Send raw TCP commands to any device. "
            "Define commands in the device config."
        ),
        "transport": "tcp",
        "default_config": {
            "host": "",
            "port": 23,
            "delimiter": "\\r\\n",
            "inter_command_delay": 0.0,
            "commands": {},
        },
        "config_schema": {
            "host": {"type": "string", "required": True, "label": "IP Address"},
            "port": {"type": "integer", "default": 23, "label": "Port"},
            "delimiter": {
                "type": "string",
                "default": "\\r\\n",
                "label": "Delimiter",
            },
            "inter_command_delay": {
                "type": "number",
                "default": 0.0,
                "label": "Inter-Command Delay (sec)",
            },
            "commands": {
                "type": "object",
                "default": {},
                "label": "Command Map (name -> raw string)",
            },
        },
        "state_variables": {},
        "commands": {},
    }

    def _command_map(self) -> dict[str, str]:
        """Return the configured command map as a dict.

        The map is authored as a JSON object in the device config. A
        hand-edited or AI-written config can store it as a JSON string or a
        non-object — coerce/guard here so a command lookup gives a clear,
        logged error instead of an ``AttributeError`` from ``str.get``.
        """
        commands = self.config.get("commands", {})
        if isinstance(commands, str):
            if not commands.strip():
                return {}
            try:
                commands = json.loads(commands)
            except (ValueError, TypeError):
                log.error(
                    f"[{self.device_id}] 'commands' config is not valid JSON "
                    f"— no commands available until it's fixed"
                )
                return {}
        if not isinstance(commands, dict):
            log.error(
                f"[{self.device_id}] 'commands' config must be a "
                f"name -> string map, got {type(commands).__name__} "
                f"— no commands available"
            )
            return {}
        return commands

    async def send_command(
        self, command: str, params: dict[str, Any] | None = None
    ) -> Any:
        """
        Send a named command. Looks up the raw string from the config's
        commands map and substitutes any parameters.
        """
        params = params or {}

        if not self.transport or not self.transport.connected:
            raise ConnectionError(f"[{self.device_id}] Not connected")

        commands = self._command_map()
        raw_cmd = commands.get(command)

        if raw_cmd is None:
            log.warning(f"[{self.device_id}] Unknown command: {command}")
            return

        # Substitute parameters using safe substitution (unknown placeholders preserved)
        def _replace(m: re.Match) -> str:
            key = m.group(1)
            if key in params:
                return str(params[key])
            return m.group(0)

        formatted = re.sub(r"\{(\w+)\}", _replace, str(raw_cmd))

        data = encode_escape_sequences(formatted)
        await self.transport.send(data)
        log.debug(f"[{self.device_id}] Sent command '{command}': {data!r}")

    async def on_data_received(self, data: bytes) -> None:
        """Log received data and emit a response event."""
        text = data.decode("ascii", errors="replace")
        log.info(f"[{self.device_id}] Received: {text}")
        await self.events.emit(
            f"device.response.{self.device_id}",
            {"data": text, "raw": data.hex()},
        )
