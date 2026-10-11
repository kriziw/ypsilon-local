"""Issue #22 model-14 evidence: reported byte pairs, not a captured raw frame."""
from unittest.mock import AsyncMock, Mock

import pytest

from .helpers import load, run

models = load("models")
codec = load("runxin.f79d")
client_mod = load("runxin.client")
framing = load("runxin.framing")


def test_model14_beta_keeps_permissions_and_pending_writes_separate():
    model = models.controller_model(14)
    assert model.support_level == "beta"
    assert model.protocol_profile == "f79d"
    assert not model.read_only
    assert model.allowed_write_fields == models.EXISTING_CONTROL_FIELDS
    assert model.hardware_verified_write_fields == (4, 6, 10, 43)
    assert model.pending_write_fields == (7, 34, 47)
    assert "contributor reports" in model.evidence
    assert "F136" in model.model_name
    assert 49 not in model.allowed_write_fields
    assert models.model_support_details(14)["resin_volume_scale_confirmed"]


def test_model14_reported_pairs_match_controller_and_app():
    # Diagnostics/read-only report: issuecomment-6054949209.
    # Controller photo: issuecomment-6084624961 shows 30.0 L.
    # https://github.com/Danirv/runxin-local/issues/22
    data = codec.decode_tlvs({26: (44, 1), 7: (1, 94), 47: (4, 1), 1: (14, 0)})
    assert data["resinVolume"] == 300
    assert data["_raw_resinVolumeBytes"] == (44, 1)
    assert models.resin_volume_litres(data["resinVolume"], 14) == 30.0
    assert data["flowRateOff"] == 350  # hundredths: 3.5 m³/h
    assert data["rawWaterHardness"] == 260


@pytest.mark.parametrize("model,raw,expected", [(9, (24, 0), 24), (12, (250, 0), 25.0)])
def test_existing_hardware_resin_observations_stay_unchanged(model, raw, expected):
    data = codec.decode_tlvs({1: (model, 0), 26: raw})
    assert models.resin_volume_litres(data["resinVolume"], model) == expected
    assert data["_raw_resinVolumeBytes"] == raw


@pytest.mark.parametrize("model", [1, 9, 12, 15, None])
def test_nonzero_high_byte_override_is_limited_to_model14(model):
    tlvs = {26: (44, 1)}
    if model is not None:
        tlvs[1] = (model, 0)
    assert codec.decode_tlvs(tlvs)["resinVolume"] == 44


def test_partial_resin_read_uses_previously_received_model_without_extra_io():
    # Synthetic response wrappers around reported byte pairs.
    transport = Mock(transact=AsyncMock(), transact_write=AsyncMock(), invalidate=AsyncMock(), close=AsyncMock())
    transport.transact.side_effect = [
        framing.build_frame(framing.QUERY_RESPONSE_CODE, [1, 14, 0]),
        framing.build_frame(framing.QUERY_RESPONSE_CODE, [26, 44, 1]),
    ]
    client = client_mod.F79DClient(transport)
    run(client.read_identity())
    assert run(client.read_fields([26]))["resinVolume"] == 300
    assert transport.transact.await_count == 2
    assert codec.decode_tlvs({26: (44, 1), 1: (9, 0)}, device_model=14)["resinVolume"] == 44


def test_invalid_reply_does_not_cache_model_context():
    transport = Mock(transact=AsyncMock(), transact_write=AsyncMock(), invalidate=AsyncMock(), close=AsyncMock())
    transport.transact.side_effect = [
        framing.build_frame(framing.WRITE_RESPONSE_CODE, [1, 14, 0]),
        framing.build_frame(framing.QUERY_RESPONSE_CODE, [26, 44, 1]),
    ]
    client = client_mod.F79DClient(transport)
    with pytest.raises(client_mod.RunxinProtocolError):
        run(client.read_identity())
    assert run(client.read_fields([26]))["resinVolume"] == 44


def test_model12_adds_f105_name_without_changing_entry_title_or_policy():
    model = models.controller_model(12)
    assert model.title == "Euro-Clear Midnight"
    assert "F105" in model.model_name
    assert model.support_level == "alpha"
    assert model.allowed_write_fields == models.EXISTING_CONTROL_FIELDS
