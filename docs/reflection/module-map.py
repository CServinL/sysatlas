"""Reflection demo: sysatlas reads sysatlas's own source and renders it.

Backward flow end-to-end. AST-only — no execution of the scanned tree.
Demonstrates the loop a coding assistant should run after any structural
change: reflect the source, save the diagram, commit it.

Uses `to_system(...)` (multi-view) rather than `to_system_map()` —
sysatlas's own bounded-complexity principle says ~25 modules don't fit
on a single canvas. One view per top sub-package; cross-package imports
become depends_on trace links between views.

Run: python docs/reflection/module-map.py
"""
from pathlib import Path

import sysatlas

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "sysatlas"
OUT = Path(__file__).with_suffix(".html")

r = sysatlas.reflect(SOURCE)
s = r.to_system(title="sysatlas — reflected from source")
s.save(str(OUT))
print(f"[sysatlas] wrote {OUT}")
