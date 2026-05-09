"""MAC OUI lookup for device manufacturer identification.

Core ships an empty table; entries come from each loaded driver's
``discovery.oui:`` hint at startup (and the community catalog refresh).
The category string attached to each OUI prefix comes from the same
driver's ``category`` field in its registry entry — drivers
self-describe as ``audio``, ``display``, ``projector``, etc., and the
discovery scanner reuses that label as a UI hint when the OUI matches
but no fingerprint identifies the device.
"""

from __future__ import annotations

from server.discovery.oui_data import AV_OUI_TABLE


class OUIDatabase:
    """Lookup MAC address manufacturer from OUI prefix."""

    def __init__(self) -> None:
        # Start with whatever ships in oui_data (empty by default), then
        # extend at runtime via add_prefix() as drivers register hints.
        self._table = dict(AV_OUI_TABLE)

    def lookup(self, mac: str) -> tuple[str, str] | None:
        """Lookup manufacturer and category from a MAC address.

        Args:
            mac: MAC address in any common format
                 (00:11:22:33:44:55, 00-11-22-33-44-55, 001122334455)

        Returns:
            (manufacturer_name, category_hint) or None if no driver hint
            registered the OUI prefix.
        """
        normalized = self._normalize_mac(mac)
        if not normalized:
            return None
        prefix = normalized[:8]  # "00:11:22"
        return self._table.get(prefix)

    def add_prefix(self, prefix: str, manufacturer: str, category: str) -> None:
        """Add a MAC OUI prefix to the lookup table.

        Only adds if the prefix is not already present — earlier
        registrations win, so an installed driver's hint isn't
        overwritten by a colliding catalog entry.
        """
        normalized = prefix.strip().lower().replace("-", ":")
        if len(normalized) == 8 and normalized not in self._table:
            self._table[normalized] = (manufacturer, category)

    @staticmethod
    def _normalize_mac(mac: str) -> str | None:
        """Normalize MAC to lowercase colon-separated format."""
        mac = mac.strip().lower()
        # Remove common separators
        clean = mac.replace("-", "").replace(":", "").replace(".", "")
        if len(clean) != 12:
            return None
        # Re-insert colons
        return ":".join(clean[i : i + 2] for i in range(0, 12, 2))
