"""Standalone discovery/authentication reports exclude private device data."""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, Mock

import broadlink.exceptions
import pytest

from scripts import debug_connection

from .helpers import run


@pytest.mark.parametrize("locked", [True, False, None])
def test_auth_rejection_report_is_sanitized_and_never_writes(monkeypatch, locked):
    secret = "192.0.2.17 02:00:00:00:00:17 device-name session-key"
    device = Mock(devtype=0x520F, is_locked=locked, name="device-name", key=b"session-key",
                  auth=AsyncMock(), get_fwversion=AsyncMock(), aclose=AsyncMock())
    device.auth.side_effect = broadlink.exceptions.AuthenticationError(-1, secret)
    hello = AsyncMock(return_value=device)
    monkeypatch.setattr(debug_connection.broadlink, "hello", hello)
    report = run(debug_connection.probe_connection("192.0.2.17"))
    assert report["discovery"] == {"ok": True, "devtype": "0x520f", "advertised_lock": locked}
    assert report["authentication"] == {
        "attempted": True, "ok": False, "error_type": "AuthenticationError", "error_code": -1,
    }
    assert report["firmware"] == {"attempted": False}
    for value in secret.split():
        assert value not in json.dumps(report)
    hello.assert_awaited_once_with("192.0.2.17", timeout=5)
    device.auth.assert_awaited_once_with()
    device.get_fwversion.assert_not_awaited()
    device.set_lock.assert_not_called()
    device.send_packet.assert_not_called()


def test_discovery_timeout_does_not_attempt_auth(monkeypatch):
    hello = AsyncMock(side_effect=broadlink.exceptions.NetworkTimeoutError(-4000, "private-host"))
    monkeypatch.setattr(debug_connection.broadlink, "hello", hello)
    report = run(debug_connection.probe_connection("192.0.2.17", timeout=10))
    assert report["discovery"]["error_code"] == -4000
    assert report["authentication"] == {"attempted": False}
    assert "private-host" not in json.dumps(report)


@pytest.mark.parametrize("firmware_fails", [False, True])
def test_authenticated_probe_only_reads_firmware(monkeypatch, firmware_fails):
    device = Mock(devtype=0x520F, is_locked=True, auth=AsyncMock(),
                  get_fwversion=AsyncMock(), aclose=AsyncMock())
    device.auth.return_value = True
    if firmware_fails:
        device.get_fwversion.side_effect = broadlink.exceptions.CommandNotSupportedError(-4, "private-host")
    else:
        device.get_fwversion.return_value = 62016
    monkeypatch.setattr(debug_connection.broadlink, "hello", AsyncMock(return_value=device))
    report = run(debug_connection.probe_connection("192.0.2.17"))
    assert report["authentication"] == {"attempted": True, "ok": True}
    assert report["firmware"]["ok"] is not firmware_fails
    if not firmware_fails:
        assert report["firmware"]["version"] == 62016
    assert "private-host" not in json.dumps(report)
    device.set_lock.assert_not_called()
    device.send_packet.assert_not_called()
    device.get_fwversion.assert_awaited_once_with()


def test_false_auth_result_is_reported_without_firmware_read(monkeypatch):
    device = Mock(devtype=0x520F, is_locked=False, auth=AsyncMock(),
                  get_fwversion=AsyncMock(), aclose=AsyncMock())
    device.auth.return_value = False
    monkeypatch.setattr(debug_connection.broadlink, "hello", AsyncMock(return_value=device))
    report = run(debug_connection.probe_connection("192.0.2.17"))
    assert report["authentication"]["ok"] is False
    assert report["firmware"] == {"attempted": False}
    device.get_fwversion.assert_not_awaited()


@pytest.mark.parametrize("value", ["0", "-1", "61", "nan", "inf"])
def test_cli_timeout_is_bounded(value):
    with pytest.raises(debug_connection.argparse.ArgumentTypeError):
        debug_connection._timeout(value)


@pytest.mark.parametrize("authenticated,status", [(True, 0), (False, 1)])
def test_cli_prints_only_report_and_reports_handshake_outcome(monkeypatch, capsys, authenticated, status):
    report = {"authentication": {"ok": authenticated}, "firmware": {"ok": False}}
    probe = AsyncMock(return_value=report)
    monkeypatch.setattr(debug_connection, "probe_connection", probe)
    monkeypatch.setattr(sys, "argv", ["debug_connection.py", "192.0.2.17", "--timeout", "10"])
    assert debug_connection.main() == status
    output = capsys.readouterr()
    assert json.loads(output.out) == report
    assert "192.0.2.17" not in output.out + output.err
    probe.assert_awaited_once_with("192.0.2.17", timeout=10)


@pytest.mark.parametrize("stage", ["discovery", "authentication"])
def test_cli_reports_unexpected_library_error_without_traceback_or_private_text(monkeypatch, capsys, stage):
    secret = "192.0.2.17 02:00:00:00:00:17 session-key"
    device = Mock(devtype=0x520F, is_locked=False, auth=AsyncMock(),
                  get_fwversion=AsyncMock(), aclose=AsyncMock())
    if stage == "discovery":
        hello = AsyncMock(side_effect=ValueError(secret))
    else:
        hello = AsyncMock(return_value=device)
        device.auth.side_effect = ValueError(secret)
    monkeypatch.setattr(debug_connection.broadlink, "hello", hello)
    monkeypatch.setattr(sys, "argv", ["debug_connection.py", "192.0.2.17"])
    assert debug_connection.main() == 1
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report[stage]["error_type"] == "ValueError"
    assert report[stage]["ok"] is False
    assert output.err == ""
    for value in secret.split():
        assert value not in output.out
    device.get_fwversion.assert_not_awaited()
    device.set_lock.assert_not_called()


def test_real_broadlink_short_auth_reply_is_a_sanitized_report(monkeypatch):
    device = debug_connection.broadlink.Device(("192.0.2.17", 80), bytes(6), 0x520F)
    device._exchange = AsyncMock(return_value=bytes(0x38) + bytes(16))
    device.aclose = AsyncMock()
    device.decrypt = Mock(return_value=bytes(16))
    monkeypatch.setattr(debug_connection.broadlink, "hello", AsyncMock(return_value=device))
    report = run(debug_connection.probe_connection("192.0.2.17"))
    assert report["authentication"] == {
        "attempted": True, "ok": False, "error_type": "ValueError", "error_code": None,
    }
    assert report["firmware"] == {"attempted": False}
    # The command byte of each framed request: authentication only,
    # so no Runxin frame reached the wire.
    assert [call.args[0][0x26] for call in device._exchange.call_args_list] == [0x65]
