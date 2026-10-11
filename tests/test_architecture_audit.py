"""Prevent nested wire profiles or transports from eroding layer boundaries."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

spec = spec_from_file_location('runxin_audit_script', Path(__file__).resolve().parents[1] / 'scripts/audit.py')
audit = module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize('relative,source', [
    ('runxin/nested/codec.py', 'from ..fields import FieldCodec'),
    ('runxin/framing.py', 'import struct'),
    ('runxin/client.py', 'from . import errors'),
    ('transport/bridge.py', 'from ..runxin.errors import RunxinTransportError'),
    ('transport/bridge.py', 'from ..runxin.framing import inner_frame'),
])
def test_neutral_dependencies_and_nested_profile_imports_are_allowed(relative, source):
    assert not audit.layer_import_checks(Path(relative), source)


@pytest.mark.parametrize('relative,source', [
    ('runxin/codec.py', 'from ..api import YpsilonLocalClient'),
    ('runxin/nested/codec.py', 'from ...transport import bridge'),
    ('runxin/codec.py', 'from .. import coordinator'),
    ('runxin/codec.py', 'import socket'),
    ('runxin/codec.py', 'import broadlink'),
    ('runxin/codec.py', 'from homeassistant.core import HomeAssistant'),
    ('runxin/codec.py', 'import requests'),
    ('transport/bridge.py', 'from ..runxin import f79d'),
    ('transport/bridge.py', 'from ..runxin.fields import FieldCodec'),
    ('transport/base.py', 'import broadlink'),
    ('transport/bridge.py', 'from ..api import YpsilonLocalClient'),
    ('transport/bridge.py', 'from .. import models'),
])
def test_layer_dependencies_are_rejected_before_they_enter_runtime(relative, source):
    assert audit.layer_import_checks(Path(relative), source)
