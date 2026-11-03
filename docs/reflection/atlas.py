"""sysatlas self-portrait, holistic text form: the architecture atlas.

A deterministic, token-cheap Markdown digest of how sysatlas is modularized —
packages, per-module purpose and public symbols, dependency structure, layers,
import cycles, coupling hotspots. Same source tree → identical output, so it is
committed and refreshed on structural change.

Unlike module-map.py this keeps the layout/render pipeline in view — how those
modules are split is part of the story the atlas exists to tell.

Component purposes and patterns come from intent.json (written by hand or by the
sysatlas-document skill); everything else is generated.

Run: python docs/reflection/atlas.py
"""
from pathlib import Path

import sysatlas

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "sysatlas"
OUT = Path(__file__).with_name("atlas.md")
INTENT = Path(__file__).with_name("intent.json")

r = sysatlas.reflect(SOURCE)  # hints auto-load from sysatlas/sysatlas.json
r.save_atlas(OUT, title="sysatlas", intent=INTENT)
print(f"[sysatlas] wrote {OUT}")
