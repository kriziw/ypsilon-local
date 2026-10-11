# Third-party software

Ypsilon depends at runtime on the `broadlink` Python module, installed from the `python-broadlink` distribution (`python-broadlink==1.0.6`), which Home Assistant installs from its own package source and which is not vendored in this repository. That distribution is `DAB-LABS/python-broadlink`, a maintained fork of the original `mjg59/python-broadlink`; both are MIT-licensed. The import name remains `broadlink`.

Home Assistant Core 2026.10 and later require the same distribution. Requiring the older `broadlink` distribution alongside it overwrites shared files in `site-packages/broadlink/` and breaks whichever copy loses, so the pin here is deliberately the same one core uses.

Home Assistant and HACS are separate projects with their own licenses and trademarks. No Home Assistant, HACS, BroadLink, ATH, BWT or Runxin source code, firmware or application binaries are redistributed here.
