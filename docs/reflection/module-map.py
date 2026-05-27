"""Reflection demo: sysatlas reads sysatlas's own source and renders it.

Backward flow end-to-end. AST-only — no execution of the scanned tree.
Demonstrates the loop a coding assistant should run after any structural
change: reflect the source, save the diagram, commit it.

Uses `to_system_map()` for a single-view module map. sysatlas itself
exceeds the bounded-complexity budget (~15 components), so running this
will emit a UserWarning suggesting `to_system()` for a multi-view split
— that warning is part of what this demo shows.

Run: python docs/reflection/module-map.py
"""
from pathlib import Path

import sysatlas

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "sysatlas"
OUT = Path(__file__).with_suffix(".html")

r = sysatlas.reflect(SOURCE)
s = r.to_system_map(title="sysatlas — reflected from source")
s.save(str(OUT))
print(f"[sysatlas] wrote {OUT}")
