"""Read-only compatibility collection with real BroadLink auth/AES and fake I/O."""
from contextlib import redirect_stderr
import io
import json
import time
import threading
import unittest
from unittest.mock import AsyncMock, patch

from broadlink.device import Device
from .helpers import load, run

probe = load("compatibility")
framing = load("runxin.framing")
f79d = load("runxin.f79d")

IDENTITY = bytes.fromhex("5a5c1f00000000000000000001c00a9f00dffd0cc9010c00220000e0dedda5")
STATE = bytes.fromhex(
    "5a5cb200000000000000000001c00a9f00dffd9fc9010c00020000030100040b130500000600000700c808020009ff"
    "000a00000b00000c00000d01000e01000f0200100000112d0012000013081e1400001503001600001707001802001"
    "92c011afa001b00001c00001d00001e00001f000020000021000022000023000024031225000026000727000028004e"
    "2900002a03e82b17002c00002d00002e00002fa000300000310000320000330000fcdea8a5"
)


class MockWireDevice(Device):
    """No sockets: preserve library auth, AES and firmware decoding."""

    def __init__(self, values=None, auth_error=0, handler=None):
        super().__init__(("192.0.2.17", 80), "020000000017", 0x520F,
                         name="PRIVATE_DEVICE_NAME", is_locked=bool(auth_error))
        self.values = values or {f: (0, 0) for f in range(1, 53)}
        self.auth_error = auth_error
        self.handler = handler
        self.calls = []
        self.session_key = bytes.fromhex("11112222333344445555666677778888")

    async def send_packet(self, packet_type, payload):
        self.calls.append((packet_type, bytes(payload)))
        self.count = ((self.count + 1) | 0x8000) & 0xFFFF
        error = 0
        if packet_type == 0x65:
            plaintext = (123456).to_bytes(4, "little") + self.session_key
            error = self.auth_error
        elif payload == b"\x68":
            plaintext = b"\x00" * 4 + (62016).to_bytes(2, "little")
        else:
            request = bytes(payload[2:])
            inner = framing.inner_frame(request)
            if inner[3] != 0x09:
                raise AssertionError("A write reached the fake wire")
            fields = list(inner[4:-2])
            selected = {f: self.values[f] for f in fields if f in self.values}
            if self.handler:
                selected, error = self.handler(fields, selected)
            triples = [byte for f, pair in sorted(selected.items()) for byte in (f, *pair)]
            frame = framing.build_frame(0xC9, triples)
            plaintext = len(frame).to_bytes(2, "little") + frame
        body = b"" if error else self.encrypt(plaintext + bytes((-len(plaintext)) % 16))
        header = bytearray(0x38)
        header[:8] = bytes.fromhex("5aa5aa555aa5aa55")
        header[0x22:0x24] = int(error).to_bytes(2, "little", signed=True)
        header[0x24:0x26] = self.devtype.to_bytes(2, "little")
        header[0x26:0x28] = (0x03E9 if packet_type == 0x65 else 0x03EE).to_bytes(2, "little")
        header[0x28:0x2A] = self.count.to_bytes(2, "little")
        header[0x2A:0x30] = self.mac[::-1]
        response = header + body
        response[0x20:0x22] = (sum(response, 0xBEAF) & 0xFFFF).to_bytes(2, "little")
        return bytes(response)


def run_device(device):
    with patch("broadlink.hello", new_callable=AsyncMock, return_value=device), redirect_stderr(io.StringIO()):
        return run(probe.probe("192.0.2.17"))


class ProbeValidation(unittest.TestCase):
    def test_cancellation_stops_before_discovery(self):
        cancel = threading.Event()
        cancel.set()
        with patch("broadlink.hello", new_callable=AsyncMock) as hello:
            report = run(probe.probe("192.0.2.17", cancel=cancel))
        hello.assert_not_called()
        self.assertEqual(report["summary"]["status"], "cancelled")

    def test_cancellation_during_reads_preserves_partial_report(self):
        cancel = threading.Event()
        def handler(fields, selected):
            cancel.set()
            return selected, 0
        device = MockWireDevice(handler=handler)
        with patch("broadlink.hello", new_callable=AsyncMock, return_value=device):
            report = run(probe.probe("192.0.2.17", cancel=cancel))
        self.assertEqual(report["summary"]["fields_observed_count"], 2)
        self.assertEqual(report["scan_stop_reason"], "cancelled")
        self.assertEqual(len(device.calls), 3)  # auth, firmware, identity

    def test_invalid_identity_response_does_not_expand_to_full_scan(self):
        device = MockWireDevice()
        original = device.send_packet
        def invalid(packet_type, payload):
            reply = bytearray(original(packet_type, payload))
            if packet_type == 0x6A and payload != b"\x68":
                reply[-1] ^= 1
            return bytes(reply)
        device.send_packet = invalid
        report = run_device(device)
        self.assertEqual(report["summary"]["fields_observed_count"], 0)
        self.assertEqual(len(device.calls), 3)
        self.assertEqual(report["scan_stop_reason"], "invalid_broadlink_packet_checksum")

    def test_wrong_transport_never_authenticates_or_queries(self):
        device = MockWireDevice()
        device.devtype = 0x1234
        report = run_device(device)
        self.assertEqual(device.calls, [])
        self.assertFalse(report["authentication"]["attempted"])

    def test_name_lookup_never_enables_unknown_models_or_exports_identifier(self):
        values={field:(0,0) for field in range(1,53)}
        values[1]=(15,0)
        identifiers=[]
        with patch("broadlink.hello", new_callable=AsyncMock, return_value=MockWireDevice(values)):
            report=run(probe.probe("192.0.2.17", identifier_sink=identifiers))
        self.assertEqual(report["controller"]["manufacturer_protocol_name"],"F138")
        self.assertFalse(report["controller"]["supported_for_normal_use"])
        self.assertEqual(identifiers,["020000000017"])
        self.assertNotIn(identifiers[0],json.dumps(report))

    def test_queries_match_repository_wire_frames(self):
        for fields in ([1], [1, 34], list(range(1, 53)), [8, 35, 36]):
            self.assertEqual(probe.build_read(fields), f79d.build_query(fields))

    def test_real_identity_and_state_fixtures_match_reference_decoder(self):
        for fixture in (IDENTITY, STATE):
            tlvs, _ = probe.parse_read(fixture)
            decoded = f79d.decode_frame(fixture)
            for field, pair in tlvs.items():
                record = probe.describe_field(field, pair, tlvs)
                name = record["name"]
                if name in decoded:
                    self.assertEqual(record["reference_value"], decoded[name], name)
                self.assertEqual(record["raw_byte_pair"], list(pair))
        tlvs, _ = probe.parse_read(STATE)
        self.assertEqual(probe.describe_field(26, tlvs[26], tlvs)["reference_value"], 250)
        self.assertIsNone(probe.describe_field(26, tlvs[26], tlvs)["reference_unit_hint"])

    def test_auth_fw_and_unknown_model_all_52_without_home_assistant(self):
        values = {f: (0, 0) for f in range(1, 53)}
        values.update({1: (15, 0), 8: (2, 0), 9: (255, 0), 52: (0x2C, 0x01)})
        device = MockWireDevice(values)
        report = run_device(device)
        self.assertTrue(report["authentication"]["ok"])
        self.assertEqual(report["firmware"]["version"], 62016)
        self.assertEqual(report["identity"]["device_model_code"], 15)
        self.assertEqual(report["summary"]["status"], "complete")
        self.assertEqual(report["summary"]["fields_observed_count"], 52)
        fields = {f["field_id"]: f for f in report["fields"]}
        self.assertEqual(fields[52]["reference_value"], 300)
        self.assertEqual(fields[9]["reference_value"], 255)
        self.assertFalse(fields[9]["enum_code_is_mapped"])
        for packet_type, payload in device.calls:
            probe.guard_outbound(packet_type, payload)

    def test_no_identifiers_keys_or_exception_text_in_report(self):
        device = MockWireDevice(auth_error=-1)
        report = run_device(device)
        self.assertEqual(report["summary"]["status"], "authentication_failed")
        self.assertEqual(len(device.calls), 1)
        text = json.dumps(report)
        for secret in ("192.0.2.17", "020000000017", "PRIVATE_DEVICE_NAME",
                       device.session_key.hex(), "123456"):
            self.assertNotIn(secret, text)
        err = RuntimeError("192.0.2.17 PRIVATE_DEVICE_NAME SECRET_TOKEN")
        self.assertNotIn("SECRET_TOKEN", json.dumps(probe.safe_error(err)))

    def test_guard_blocks_writes_unlock_and_reset_before_wire(self):
        device = MockWireDevice()
        probe.ReadSession(device, 5, time.monotonic() + 20)
        write = f79d.build_write_fields({34: 1})
        for packet_type, payload in (
            (0x6A, len(write).to_bytes(2, "little") + write),
            (0x6A, bytes(0x50)), (0x6A, b"\x72"), (0x66, bytes(16)),
        ):
            with self.assertRaises(probe.ProbeError):
                device.send_packet(packet_type, payload)
        self.assertEqual(device.calls, [])

    def test_bulk_failure_falls_back_and_recovers_all_fields(self):
        def handler(fields, selected):
            if len(fields) > 16:
                raise TimeoutError("PRIVATE_HOST SECRET_SESSION")
            return selected, 0
        report = run_device(MockWireDevice(handler=handler))
        self.assertEqual(report["summary"]["status"], "complete")
        self.assertTrue(any(q["phase"] == "fallback_group" for q in report["queries"]))
        self.assertNotIn("PRIVATE_HOST", json.dumps(report))

    def test_missing_model_is_not_replaced_with_zero_or_guessed_model(self):
        values = {f: (0, 0) for f in range(2, 53)}
        report = run_device(MockWireDevice(values))
        self.assertEqual(report["summary"]["status"], "partial")
        self.assertFalse(report["identity"]["device_model_present"])
        self.assertIsNone(report["identity"]["device_model_code"])
        self.assertEqual(report["summary"]["fields_not_returned"], [1])
        self.assertTrue(any(q["phase"] == "identity_single_field" for q in report["queries"]))

    def test_partial_zero_false_and_field52_absence_are_preserved(self):
        values = {f: (0, 0) for f in range(1, 52)}
        report = run_device(MockWireDevice(values))
        fields = {f["field_id"]: f for f in report["fields"]}
        self.assertEqual(fields[1]["reference_value"], 0)
        self.assertIs(fields[49]["reference_value"], False)
        self.assertEqual(report["summary"]["fields_not_returned"], [52])

    def test_unit_and_volume_bytes_from_different_responses_are_not_combined(self):
        def handler(fields, selected):
            if 35 in fields:
                selected.pop(8, None)
                selected.pop(36, None)
            return selected, 0
        report = run_device(MockWireDevice(handler=handler))
        for query in report["queries"]:
            for record in query.get("fields", []):
                if record["field_id"] == 35:
                    self.assertIsNone(record["reference_value"])
                    self.assertIn("unit_or_continuation_missing_in_same_response",
                                  record["interpretation_warnings"])

    def test_malformed_checksum_and_write_ack_rejected(self):
        malformed = bytearray(IDENTITY)
        malformed[-2] ^= 1
        for frame in (bytes(malformed), framing.build_frame(0xD9, [])):
            with self.assertRaises(probe.ProbeError):
                probe.parse_read(frame)

    def test_deadline_and_budget_stop_reads(self):
        device = MockWireDevice()
        session = probe.ReadSession(device, 5, time.monotonic() - 1)
        with self.assertRaises(probe.ProbeError):
            session.read([1])
        self.assertEqual(device.calls, [])
        session.deadline = time.monotonic() + 20
        session.query_count = probe.MAX_QUERIES
        with self.assertRaises(probe.ProbeError):
            session.read([1])
        self.assertEqual(device.calls, [])

    def test_transient_error_only_retries_once(self):
        failures = 0
        def handler(fields, selected):
            nonlocal failures
            if fields == [1, 34] and failures < 1:
                failures += 1
                return {}, -5
            return selected, 0
        with patch.object(probe.time, "sleep", lambda _: None):
            report = run_device(MockWireDevice(handler=handler))
        self.assertEqual(report["summary"]["status"], "complete")
        self.assertEqual(report["summary"]["transient_retries"], 1)

    def test_interruption_preserves_observations(self):
        def handler(fields, selected):
            if len(fields) == 52:
                raise KeyboardInterrupt
            return selected, 0
        report = run_device(MockWireDevice(handler=handler))
        self.assertTrue(report["interrupted"])
        self.assertEqual(report["summary"]["fields_observed_count"], 2)
        self.assertEqual(len(report["fields"]), 2)

    def test_counter_mismatch_stops_authentication_before_any_query(self):
        device = MockWireDevice()
        original = device.send_packet
        def wrong_counter(packet_type, payload):
            reply = original(packet_type, payload)
            device.count += 1
            return reply
        device.send_packet = wrong_counter
        report = run_device(device)
        self.assertFalse(report["authentication"]["ok"])
        self.assertEqual(report["authentication"]["error"]["reason"], "broadlink_counter_mismatch")
        self.assertEqual(len(device.calls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
