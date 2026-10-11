"""Offline consistency, protocol and architecture regression audit."""
from __future__ import annotations

import ast
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import types

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "custom_components" / "ypsilon_local"
AUDIT_PKG = "_ypsilon_audit"
PLATFORMS = {
    "sensor.py": "sensor",
    "binary_sensor.py": "binary_sensor",
    "number.py": "number",
    "button.py": "button",
    "time.py": "time",
}
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def read(path: str) -> str:
    return (HERE / path).read_text()


def _ensure_package() -> None:
    if AUDIT_PKG not in sys.modules:
        root = types.ModuleType(AUDIT_PKG)
        root.__path__ = [str(HERE)]
        sys.modules[AUDIT_PKG] = root
    name = f"{AUDIT_PKG}.runxin"
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(HERE / "runxin")]
        sys.modules[name] = pkg


def load_runxin(name: str):
    _ensure_package()
    full = f"{AUDIT_PKG}.runxin.{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, HERE / "runxin" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runxin/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


def protocol_checks() -> list[str]:
    errors: list[str] = []
    try:
        p = load_runxin("f79d")
        fields_mod = load_runxin("fields")
        semantics = load_runxin("semantics")
    except Exception as err:  # noqa: BLE001
        return [f"PROTOCOL load failed: {err}"]

    def req(ok: bool, msg: str) -> None:
        if not ok:
            errors.append(f"PROTOCOL {msg}")

    req(p.encode_field(43, 50) == [43, 50, 0], "field43 encoding")
    req(p.encode_field(47, 400) == [47, 0x90, 0x01], "field47 encoding")
    req(p.encode_field(7, 200) == [7, 0x00, 0xC8], "field7 must be big-endian")
    req(p.encode_field(10, (2, 30)) == [10, 2, 30], "field10 encoding")
    req(p.encode_field(49, 1) == [49, 1, 0], "field49 legacy codec encoding")
    req(p.WRITE_U16 == {25, 47, 52}, "WRITE_U16 set")
    req(p.WRITE_U16_BE == {7}, "WRITE_U16_BE field7")
    req(p.BE16_FIELDS == {7, 11}, "fields 7 and 11 must read as BE16")
    req({12, 25, 47, 52}.issubset(p.LE16_FIELDS), "LE16 field set")
    req(7 not in p.LE16_FIELDS, "field7 must not remain in LE16 set")

    d = p.decode_tlvs({7: (0x03, 0xE8), 11: (0x03, 0xE8)})
    req(d.get("flowRateOff") == 1000, "field7 BE decode")
    req(d.get("_raw_flowRateOff") == 1000, "field7 raw BE decode")
    req(d.get("flowRate") == 1000, "field11 BE decode")
    req((0x03 | (0xE8 << 8)) == 59395, "field7 historical LE regression vector")
    req(((0x03 << 8) | 0xE8) == 1000, "field7 physical BE regression vector")

    req(
        p.decode_tlvs({35: (0, 1), 36: (59, 2)}).get("residualWaterProduction") is None,
        "volume without unit must fail closed",
    )
    d2 = p.decode_tlvs({8: (2, 0), 35: (0, 1), 36: (59, 2)})
    req(d2.get("residualWaterProduction") == 159.02, "unit2 base100 volume")
    expected = 2 | (59 << 8) | (1 << 16)
    for unit in (0, 1):
        du = p.decode_tlvs({8: (unit, 0), 35: (0, 1), 36: (59, 2)})
        req(du.get("residualWaterProduction") == expected, f"unit{unit} 24bit volume")

    evidence = fields_mod.Evidence
    by_id = fields_mod.F79D_FIELDS_BY_ID
    for field in (4, 6, 7, 10, 43, 47):
        req(evidence.HARDWARE_WRITE_VERIFIED in by_id[field].evidence, f"field{field} HW evidence")
    for field in (34, 49):
        req(evidence.HARDWARE_WRITE_VERIFIED not in by_id[field].evidence, f"field{field} must stay pending HW")
    req("03 E8" in (by_id[7].notes or ""), "field7 physical wire evidence note")
    req("not a measured remaining salt level" in (by_id[43].notes or ""), "field43 salt semantics")
    req("not the vendor app's week-history total" in (by_id[39].notes or ""), "field39 weekly semantics")
    req(p.STATE_FIELDS == list(range(1, 52)), "normal state block must remain fields 1..51")
    req(52 not in p.STATE_FIELDS, "field52 must remain on separate slow refresh policy")

    req(semantics.vacation_status(False, 0) == "off", "vacation off semantics")
    req(semantics.vacation_status(True, 3) == "preparing", "vacation preparing semantics")
    req(semantics.vacation_status(True, 8) == "active", "vacation active semantics")
    req(semantics.SYSTEM_CLOSE_REASON_KEYS.get(513) == "leak_detected", "close reason 513")
    req(semantics.SYSTEM_CLOSE_REASON_KEYS.get(769) == "continuous_flow_timeout", "close reason 769")
    req(semantics.SYSTEM_CLOSE_REASON_KEYS.get(1025) == "flow_rate_exceeded", "close reason 1025")
    return errors


def layer_import_checks(relative: Path, source: str) -> list[str]:
    """Keep wire codecs reusable, including nested profiles and relative imports."""
    errors: list[str] = []
    package = relative.parts[:-1]
    layer = package[0]
    for node in ast.walk(ast.parse(source)):
        modules: list[str] = []
        outside_package = False
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                outside_package = node.level > len(package)
                base = package[:len(package) - node.level + 1] if node.level <= len(package) else ()
                if layer == "runxin" and (not base or base[0] != "runxin"):
                    errors.append(f"{relative} imports outside the pure runxin package")
                    continue
                prefix = ".".join((*base, *(node.module or "").split("."))).strip(".")
            else:
                prefix = node.module or ""
            modules = [prefix, *(f"{prefix}.{alias.name}".strip(".") for alias in node.names)]
        for module in modules:
            root = module.split(".")[0]
            bad = root == "homeassistant"
            if layer == "runxin":
                bad |= root in {"broadlink", "socket", "requests", "aiohttp", "httpx", "urllib", "http", "transport", "custom_components"}
            if layer == "transport":
                bad |= root == "custom_components" or (outside_package and root != "runxin")
                if root == "runxin":
                    # Neutral errors/framing are allowed, field/semantic maps are not.
                    bad |= module != "runxin" and not any(
                        module == allowed or module.startswith(allowed + ".")
                        for allowed in ("runxin.errors", "runxin.framing")
                    )
                if relative == Path("transport/base.py"):
                    bad |= root == "broadlink"
            if bad:
                errors.append(f"{relative} imports forbidden layer dependency {module}")
    return sorted(set(errors))


def architecture_checks() -> list[str]:
    errors: list[str] = []
    required = [
        "runxin/__init__.py", "runxin/errors.py", "runxin/fields.py", "runxin/framing.py",
        "runxin/f79d.py", "runxin/client.py", "runxin/semantics.py",
        "transport/__init__.py", "transport/base.py", "transport/broadlink_bl3372.py",
    ]
    for rel in required:
        if not (HERE / rel).exists():
            errors.append(f"missing architecture module: {rel}")
    for folder in ("runxin", "transport"):
        for path in (HERE / folder).rglob("*.py"):
            errors.extend(layer_import_checks(path.relative_to(HERE), path.read_text()))
    return errors


def _png_size(path: Path) -> tuple[int, int] | None:
    """Read PNG IHDR dimensions without third-party dependencies."""
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def branding_checks() -> list[str]:
    errors: list[str] = []
    brand = HERE / "brand"
    expected = {
        "icon.png": (256, 256),
        "icon@2x.png": (512, 512),
        "dark_icon.png": (256, 256),
        "dark_icon@2x.png": (512, 512),
    }
    for name, size in expected.items():
        path = brand / name
        if not path.exists():
            errors.append(f"brand/{name} missing")
        elif _png_size(path) != size:
            errors.append(f"brand/{name} must be {size[0]}x{size[1]}, got {_png_size(path)}")

    for name in ("logo.png", "logo@2x.png", "dark_logo.png", "dark_logo@2x.png"):
        path = brand / name
        if not path.exists():
            errors.append(f"brand/{name} missing")
            continue
        size = _png_size(path)
        if size is None or size[0] <= size[1]:
            errors.append(f"brand/{name} must be a valid landscape PNG, got {size}")

    if (brand / "logo.png").exists() and (brand / "icon.png").exists():
        if (brand / "logo.png").read_bytes() == (brand / "icon.png").read_bytes():
            errors.append("brand logo must not reuse the square icon byte-for-byte")
    if _png_size(brand / "logo.png") and _png_size(brand / "logo@2x.png"):
        a = _png_size(brand / "logo.png")
        b = _png_size(brand / "logo@2x.png")
        if b != (a[0] * 2, a[1] * 2):
            errors.append(f"brand/logo@2x.png must be exact 2x logo dimensions, got {b} vs {a}")
    return errors


def repository_checks() -> list[str]:
    errors: list[str] = []
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        for action in re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", workflow.read_text(), re.M):
            if not action.startswith("./") and not re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", action):
                errors.append(f"{workflow.relative_to(ROOT)} action must use a full commit SHA: {action}")
    required = [
        "LICENSE", "NOTICE", "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
        "LEGAL.md", "THIRD_PARTY.md", "hacs.json", "info.md",
        ".github/workflows/validate.yml", ".github/workflows/hassfest.yml",
        ".github/workflows/audit.yml", ".github/workflows/release.yml",
        "docs/architecture.md", "docs/protocol.md", "docs/f79d.md", "docs/hardware-verification.md",
        "docs/waterdevice-audit.md",
    ]
    for rel in required:
        if not (ROOT / rel).exists():
            errors.append(f"missing publication file: {rel}")

    for path in HERE.rglob("*.py"):
        try:
            ast.parse(path.read_text())
        except SyntaxError as err:
            errors.append(f"SYNTAX {path.relative_to(HERE)}: {err}")
    for path in HERE.rglob("*.json"):
        try:
            json.loads(path.read_text())
        except Exception as err:  # noqa: BLE001
            errors.append(f"JSON {path.relative_to(HERE)}: {err}")

    manifest = json.loads(read("manifest.json"))
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append(f"invalid manifest version: {version!r}")
    if manifest.get("name") != "Runxin Local":
        errors.append("manifest name != Runxin Local")
    if (HERE / "strings.json").exists():
        errors.append("custom integration must not ship strings.json")

    init = read("__init__.py")
    coordinator = read("coordinator.py")
    sensors = read("sensor.py")
    services = read("services.py")
    if (HERE / "switch.py").exists():
        errors.append("integration must not expose the withdrawn vacation switch platform")
    if "Platform.SWITCH" in init:
        errors.append("switch platform still registered")
    if "async_set_vacation_mode" in coordinator or "FIELD_HOLIDAY_MODE" in coordinator:
        errors.append("unverified direct vacation write remains in coordinator")
    if "UnitOfVolumeFlowRate.LITERS_PER_HOUR" in sensors:
        errors.append("legacy WaterDevice Lpm unit regressed to L/h")
    if "UnitOfVolumeFlowRate.LITERS_PER_MINUTE" not in sensors:
        errors.append("L/min flow unit missing")
    for key in ("salt_dissolution_remaining", "pause_1_remaining"):
        m = re.search(
            rf'YpsilonSensorDescription\((?:(?!YpsilonSensorDescription).)*?key="{key}"(?P<body>.*?)\n    \),',
            sensors,
            re.S,
        )
        if not m or "EntityCategory.DIAGNOSTIC" not in m.group("body"):
            errors.append(f"{key}: diagnostic regression")
    if "FIELD_HOLIDAY_MODE" in read("const.py").split("WRITABLE_FIELDS", 1)[1].split(")", 1)[0]:
        errors.append("vacation field leaked into generic write whitelist")
    if "FIELD_SYSTEM_MODE" in read("const.py").split("WRITABLE_FIELDS", 1)[1].split(")", 1)[0]:
        errors.append("mechanical field leaked into generic write whitelist")
    if "_validate_raw_fields" not in services:
        errors.append("raw service validation missing")

    keys: dict[str, set[str]] = {}
    exception_keys: set[str] = set()
    for file, domain in PLATFORMS.items():
        text = read(file)
        exceptions = set(re.findall(r'translation_key="(\w+)",\s*\n\s*translation_placeholders', text))
        exception_keys |= exceptions
        found = set(re.findall(r'translation_key="(\w+)"', text)) | set(
            re.findall(r'_attr_translation_key = "(\w+)"', text)
        )
        found -= exceptions
        if found:
            keys[domain] = found
    exception_keys |= set(re.findall(r'translation_key="(\w+)"', services))

    names: list[tuple[str, str, str]] = []
    for lang in ("ca", "en", "es"):
        translation = json.loads(read(f"translations/{lang}.json"))
        data = translation.get("entity", {})
        if "switch" in data:
            errors.append(f"translations/{lang}.json still contains withdrawn switch translations")
        for domain, expected in keys.items():
            missing = sorted(expected - set(data.get(domain, {})))
            if missing:
                errors.append(f"translations/{lang}.json {domain}: missing {missing}")
        missing_exceptions = sorted(exception_keys - set(translation.get("exceptions", {})))
        if missing_exceptions:
            errors.append(f"translations/{lang}.json exceptions: missing {missing_exceptions}")
        stale_vacation_exceptions = {
            "vacation_enable_invalid_state", "vacation_disable_invalid_state"
        } & set(translation.get("exceptions", {}))
        if stale_vacation_exceptions:
            errors.append(
                f"translations/{lang}.json has stale vacation exceptions: {sorted(stale_vacation_exceptions)}"
            )
        if lang == "en":
            for domain, group in data.items():
                for key, value in group.items():
                    if isinstance(value, dict) and "name" in value:
                        names.append((value["name"], domain, key))
    for name, count in Counter(x[0] for x in names).items():
        if count > 1:
            errors.append(f"duplicate English entity name: {name}")
    return errors


def main() -> int:
    errors = protocol_checks() + architecture_checks() + branding_checks() + repository_checks()
    if errors:
        print("Audit failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Audit OK: protocol, architecture, branding, translations, entities and publication files are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
