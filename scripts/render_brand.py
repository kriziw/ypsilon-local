#!/usr/bin/env python3
"""Render the source SVG wordmarks; optional development-only cairosvg needed.

The existing square water icons are retained. Home Assistant uses the bundled
PNG exports; it does not need CairoSVG or run this script.
"""
from pathlib import Path

import cairosvg

BRAND = Path(__file__).resolve().parents[1] / "custom_components/ypsilon_local/brand"

if __name__ == "__main__":
    for prefix in ("", "dark_"):
        for scale, suffix in ((1, ""), (2, "@2x")):
            cairosvg.svg2png(
                url=str(BRAND / f"{prefix}logo.svg"),
                write_to=str(BRAND / f"{prefix}logo{suffix}.png"),
                scale=scale,
            )
