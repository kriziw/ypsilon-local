"""Load the pure protocol packages without importing Home Assistant."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ypsilon_local"
TEST_PKG = "_ypsilon_testpkg"


def _ensure_namespace() -> None:
    if TEST_PKG not in sys.modules:
        root = types.ModuleType(TEST_PKG)
        root.__path__ = [str(INTEGRATION)]
        sys.modules[TEST_PKG] = root
    for child in ("runxin", "transport"):
        name = f"{TEST_PKG}.{child}"
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = [str(INTEGRATION / child)]
            sys.modules[name] = pkg


def load(relative: str):
    """Load e.g. `runxin.f79d` or `transport.broadlink_bl3372`."""
    _ensure_namespace()
    full = f"{TEST_PKG}.{relative}"
    if full in sys.modules:
        return sys.modules[full]
    path = INTEGRATION.joinpath(*relative.split(".")).with_suffix(".py")
    spec = importlib.util.spec_from_file_location(full, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


_LOOP: asyncio.AbstractEventLoop | None = None


def run(coro):
    """Drive one coroutine, on a single event loop shared by the session.

    The transport contract became awaitable with `python-broadlink` 1.0, but
    `requirements-test-offline.txt` installs only `pytest` and the library -
    no `pytest-asyncio` - so the offline tests drive coroutines themselves.

    It must be ONE loop for the whole session rather than a fresh
    `asyncio.run()` per call. `asyncio.Lock` binds to the first loop that
    acquires it, and the transport, the F79D client and
    `YpsilonLocalClient` each hold one. Two `asyncio.run()` calls against
    the same object would raise "is bound to a different event loop" on the
    second - which is exactly what a test doing a read then a write does.
    """
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
    return _LOOP.run_until_complete(coro)
