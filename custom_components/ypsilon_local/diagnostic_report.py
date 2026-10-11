"""Local storage and presentation of explicitly requested compatibility reports."""
from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, REPOSITORY_URL


@dataclass(slots=True)
class DiagnosticReport:
    """A cached report only: no client, coordinator, polling or write methods."""

    report: dict[str, Any] | None


def report_store(hass: HomeAssistant, report_id: str) -> Store:
    """Use an opaque ID, never an address or hardware identifier, in the filename."""
    return Store(hass, 1, f"{DOMAIN}.compatibility.{report_id}")


def prepare_report(report: dict[str, Any]) -> dict[str, Any]:
    """Add software versions and a small issue draft using allowlisted metadata."""
    manifest = json.loads(Path(__file__).with_name("manifest.json").read_text())
    report["report_schema_version"] = 1
    report["integration"] = {"name": manifest["name"], "version": manifest["version"], "domain": DOMAIN}
    report["home_assistant_version"] = version("homeassistant")
    controller = report.get("controller") or {}
    code = controller.get("code")
    name = controller.get("manufacturer_protocol_name") or "unidentified controller"
    status = report.get("summary", {}).get("status", "unknown")
    body = (
        f"### Controller\n{name}; deviceModel={code}\n\n"
        f"### Software\nRunxin Local {manifest['version']}; Home Assistant {report['home_assistant_version']}\n\n"
        f"### Diagnostic result\n{status}\n\n"
        "### Device and independent comparison\nPlease add the brand/model and a few app/controller readings with units.\n\n"
        "### Attachment\nAttach the downloaded diagnostics JSON, even if partial. "
        "Remove identifiers from any screenshots. No credentials or packet capture are needed.\n"
    )
    report["issue_draft"] = body
    report["issue_url"] = REPOSITORY_URL + "/issues/new?" + urlencode({
        "title": f"[Device]: {name} – model {code}", "body": body,
    })
    report["next_steps"] = [
        "Download this cached report from the integration entry's diagnostics menu.",
        "Attach the JSON to the issue; add brand/capacity and app/controller values with units if convenient.",
        "A successful read does not enable this model or validate configuration writes.",
        "After support is added, delete the diagnostic entry and add the device normally.",
    ]
    return report
