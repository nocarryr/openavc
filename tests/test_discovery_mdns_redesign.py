"""Tests for the mDNS scanner additions in the discovery redesign.

Covers Evidence emission, unknown-service-type tracking via
``_services._dns-sd._udp.`` enumeration, and control-interface
binding. Existing mDNS tests in test_discovery_passive.py remain green
unchanged.
"""

from server.discovery.mdns_scanner import MDNSResult, MDNSScanner
from server.discovery.result import SignalTier
from server.discovery.ssdp_scanner import SSDPResult, SSDPScanner
from server.discovery.tier_matcher import KIND_SSDP


class TestMDNSResultEvidence:
    def test_with_service_type_emits_tier1_evidence(self):
        r = MDNSResult(
            ip="10.0.0.50",
            service_type="_netaudio-cmc._udp.local.",
            txt_records={"manufacturer": "Audinate", "id": "001122334455"},
            instance_name="Stage-Left",
        )
        ev = r.to_evidence()

        assert ev is not None
        assert ev.tier == SignalTier.PASSIVE_LISTENER
        assert ev.source == "mdns:_netaudio-cmc._udp.local."
        assert ev.data["txt"]["manufacturer"] == "Audinate"
        assert ev.data["instance"] == "Stage-Left"

    def test_a_record_only_returns_none(self):
        # A-record-only resolutions don't carry a service type and
        # cannot produce a Tier 1 identification on their own.
        r = MDNSResult(ip="10.0.0.50")
        assert r.to_evidence() is None

    def test_no_txt_records_omits_txt_field(self):
        r = MDNSResult(
            ip="10.0.0.50",
            service_type="_pjlink._tcp.local.",
        )
        ev = r.to_evidence()
        assert ev is not None
        # No TXT was observed, so the evidence carries no txt key.
        # (Filter rules can still match on no-TXT.)
        assert "txt" not in ev.data


class TestMDNSScannerControlIP:
    def test_default_no_control_ip(self):
        scanner = MDNSScanner()
        assert scanner._control_ip == ""

    def test_control_ip_passed_through(self):
        scanner = MDNSScanner(control_ip="192.168.1.50")
        assert scanner._control_ip == "192.168.1.50"


class TestUnknownServiceTypeTracking:
    def test_initial_set_is_empty(self):
        scanner = MDNSScanner()
        assert scanner.unknown_service_types == set()

    def test_track_records_new_service_type(self):
        scanner = MDNSScanner()
        scanner._track_unknown_service_type("_unknown-vendor._tcp.local.")
        assert "_unknown-vendor._tcp.local." in scanner.unknown_service_types

    def test_track_normalizes_trailing_dot(self):
        scanner = MDNSScanner()
        scanner._track_unknown_service_type("_unknown._tcp.local")
        scanner._track_unknown_service_type("_unknown._tcp.local.")
        # Both should normalize to one entry.
        types = scanner.unknown_service_types
        assert len(types) == 1
        assert "_unknown._tcp.local." in types

    def test_track_filters_out_known_types(self):
        scanner = MDNSScanner()
        # These are in AV_SERVICE_TYPES — we already query them, so
        # observing them in the enumeration is not "unknown".
        scanner._track_unknown_service_type("_pjlink._tcp.local.")
        scanner._track_unknown_service_type("_netaudio-cmc._udp.local.")
        assert scanner.unknown_service_types == set()

    def test_track_dedups(self):
        scanner = MDNSScanner()
        for _ in range(5):
            scanner._track_unknown_service_type("_some-vendor._tcp.local.")
        assert len(scanner.unknown_service_types) == 1

    def test_unknown_service_types_returns_copy(self):
        scanner = MDNSScanner()
        scanner._track_unknown_service_type("_x._tcp.local.")
        snapshot = scanner.unknown_service_types
        snapshot.clear()
        # Internal set should be untouched.
        assert "_x._tcp.local." in scanner.unknown_service_types


class TestSSDPControlIP:
    def test_default_no_control_ip(self):
        scanner = SSDPScanner()
        assert scanner._control_ip == ""

    def test_control_ip_passed_through(self):
        scanner = SSDPScanner(control_ip="192.168.1.50")
        assert scanner._control_ip == "192.168.1.50"


class TestSSDPResultEvidence:
    def test_with_st_emits_tier1_evidence(self):
        r = SSDPResult(
            ip="10.0.0.50",
            st="urn:schemas-upnp-org:device:MediaRenderer:1",
            usn="uuid:abc::urn:schemas-upnp-org:device:MediaRenderer:1",
            friendly_name="Sonos Kitchen",
            manufacturer="Sonos Inc.",
            model_name="ZP100",
        )
        ev = r.to_evidence()
        assert ev is not None
        assert ev.tier == SignalTier.PASSIVE_LISTENER
        assert ev.data["kind"] == KIND_SSDP
        assert ev.data["source_id"] == "urn:schemas-upnp-org:device:MediaRenderer:1"
        assert ev.data["manufacturer"] == "Sonos Inc."
        assert ev.data["model"] == "ZP100"

    def test_no_st_returns_none(self):
        # No ST means we can't deterministically match.
        r = SSDPResult(ip="10.0.0.50", usn="uuid:abc", friendly_name="thing")
        assert r.to_evidence() is None


class TestNewServiceTypesInQueryList:
    """Verify the corrected service-type list lands in AV_SERVICE_TYPES."""

    def test_dante_complete(self):
        from server.discovery.mdns_scanner import AV_SERVICE_TYPES
        for required in (
            "_netaudio-cmc._udp.local.",
            "_netaudio-arc._udp.local.",
            "_netaudio-chan._udp.local.",
            "_netaudio-dbc._udp.local.",
            "_workgroup._udp.local.",
        ):
            assert required in AV_SERVICE_TYPES

    def test_nmos_complete(self):
        from server.discovery.mdns_scanner import AV_SERVICE_TYPES
        for required in (
            "_nmos-node._tcp.local.",
            "_nmos-register._tcp.local.",
            "_nmos-query._tcp.local.",
            "_nmos-registration._tcp.local.",
        ):
            assert required in AV_SERVICE_TYPES

    def test_ndi_present(self):
        from server.discovery.mdns_scanner import AV_SERVICE_TYPES
        assert "_ndi._tcp.local." in AV_SERVICE_TYPES

    def test_lutron_leap_present(self):
        from server.discovery.mdns_scanner import AV_SERVICE_TYPES
        assert "_leap._tcp.local." in AV_SERVICE_TYPES

    def test_sennheiser_ssc_present(self):
        from server.discovery.mdns_scanner import AV_SERVICE_TYPES
        assert "_ssc._udp.local." in AV_SERVICE_TYPES
        assert "_ssc._tcp.local." in AV_SERVICE_TYPES

    def test_roku_present(self):
        from server.discovery.mdns_scanner import AV_SERVICE_TYPES
        assert "_roku._tcp.local." in AV_SERVICE_TYPES
