"""Reflection demo: sysatlas reads sysatlas's own source and renders it.

Backward flow end-to-end. AST-only — no execution of the scanned tree.
Demonstrates the loop a coding assistant should run after any structural
change: reflect the source, save the diagram, commit it.

Run: python docs/reflection/module-map.py
"""
from pathlib import Path

import sysatlas

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "sysatlas"
OUT = Path(__file__).with_suffix(".html")

r = (
    sysatlas.reflect(SOURCE)
    .exclude("LLM_GUIDE.md", "__init__.py", "_ontology/__init__.py")
)
m = r.to_system_map(title="sysatlas — reflected from source")
m.save(str(OUT))
print(f"[sysatlas] wrote {OUT}")
