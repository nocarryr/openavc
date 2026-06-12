"""Tests for the /proc/net/arp-based ARP harvest (discovery.network_scanner).

Synthetic content only — no real network or OS ARP table.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from server.discovery import network_scanner
from server.discovery.network_scanner import (
    _harvest_arp_linux,
    _parse_proc_net_arp,
    harvest_arp_table,
)

_HEADER = "IP address       HW type     Flags       HW address            Mask     Device\n"


class TestProcNetArpParser:
    def test_parses_complete_entries(self):
        text = _HEADER + (
            "192.168.1.1      0x1         0x2         a4:91:b1:aa:bb:cc     *        wlan0\n"
            "192.168.1.20     0x1         0x2         00:1A:2B:3C:4D:5E     *        eth0\n"
        )
        result = _parse_proc_net_arp(text)
        assert result == {
            "192.168.1.1": "a4:91:b1:aa:bb:cc",
            "192.168.1.20": "00:1a:2b:3c:4d:5e",  # normalized to lowercase
        }

    def test_skips_incomplete_entries(self):
        # Flags 0x0 = incomplete (ARP request never answered)
        text = _HEADER + (
            "192.168.1.99     0x1         0x0         00:00:00:00:00:00     *        wlan0\n"
            "192.168.1.1      0x1         0x2         a4:91:b1:aa:bb:cc     *        wlan0\n"
        )
        assert _parse_proc_net_arp(text) == {"192.168.1.1": "a4:91:b1:aa:bb:cc"}

    def test_skips_zero_mac_even_when_flags_complete(self):
        text = _HEADER + (
            "192.168.1.99     0x1         0x2         00:00:00:00:00:00     *        wlan0\n"
        )
        assert _parse_proc_net_arp(text) == {}

    def test_skips_broadcast_mac(self):
        text = _HEADER + (
            "192.168.1.255    0x1         0x2         ff:ff:ff:ff:ff:ff     *        wlan0\n"
        )
        assert _parse_proc_net_arp(text) == {}

    def test_skips_malformed_lines(self):
        text = _HEADER + (
            "garbage\n"
            "\n"
            "192.168.1.5      0x1         notahexflag a4:91:b1:aa:bb:cc     *        wlan0\n"
            "192.168.1.6      0x1         0x2         not-a-mac             *        wlan0\n"
            "192.168.1.7      0x1         0x2         a4:91:b1:aa:bb:cc     *        wlan0\n"
        )
        assert _parse_proc_net_arp(text) == {"192.168.1.7": "a4:91:b1:aa:bb:cc"}

    def test_permanent_entries_kept(self):
        # Flags 0x6 = ATF_COM | ATF_PERM (static entry) — still a valid MAC
        text = _HEADER + (
            "192.168.1.2      0x1         0x6         a4:91:b1:aa:bb:cc     *        eth0\n"
        )
        assert _parse_proc_net_arp(text) == {"192.168.1.2": "a4:91:b1:aa:bb:cc"}

    def test_empty_table(self):
        assert _parse_proc_net_arp(_HEADER) == {}


class TestHarvestArpLinux:
    async def test_reads_proc_net_arp(self, monkeypatch, tmp_path):
        arp_file = tmp_path / "arp"
        arp_file.write_text(
            _HEADER
            + "192.168.1.1      0x1         0x2         a4:91:b1:aa:bb:cc     *        wlan0\n"
        )
        monkeypatch.setattr(network_scanner, "_PROC_NET_ARP", str(arp_file))
        fallback = AsyncMock(return_value={})
        monkeypatch.setattr(network_scanner, "_harvest_arp_ip_neigh", fallback)

        result = await _harvest_arp_linux()

        assert result == {"192.168.1.1": "a4:91:b1:aa:bb:cc"}
        fallback.assert_not_awaited()

    async def test_falls_back_to_ip_neigh_when_unreadable(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            network_scanner, "_PROC_NET_ARP", str(tmp_path / "does-not-exist"),
        )
        fallback = AsyncMock(return_value={"192.168.1.9": "aa:bb:cc:dd:ee:ff"})
        monkeypatch.setattr(network_scanner, "_harvest_arp_ip_neigh", fallback)

        result = await _harvest_arp_linux()

        assert result == {"192.168.1.9": "aa:bb:cc:dd:ee:ff"}
        fallback.assert_awaited_once()

    async def test_harvest_arp_table_routes_posix_to_proc(self, monkeypatch, tmp_path):
        arp_file = tmp_path / "arp"
        arp_file.write_text(
            _HEADER
            + "10.0.0.1         0x1         0x2         11:22:33:44:55:66     *        eth0\n"
        )
        monkeypatch.setattr(network_scanner, "_IS_WINDOWS", False)
        monkeypatch.setattr(network_scanner, "_PROC_NET_ARP", str(arp_file))

        result = await harvest_arp_table()

        assert result == {"10.0.0.1": "11:22:33:44:55:66"}
