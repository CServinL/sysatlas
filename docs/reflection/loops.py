"""Conceptual view: sysatlas as read/write loops around its ontology.

Hand-authored (forward flow). Tells the story of what sysatlas *is*,
not what its files import. The module-map.py demo answers the literal
question; this one answers the conceptual one.

Three parties feed the ontology:
  - User: writes builder calls.
  - LLM: writes source code, and writes builder calls.
  - Source code: gets parsed back into ontology instances.

The ontology hub sits in the middle. Layout + Render drain it into
diagrams. The two write paths (forward — through builders, backward —
through reflection) are deliberately symmetric: that symmetry *is* the
read/write loop.

Run: python docs/reflection/loops.py
"""
from pathlib import Path

from sysatlas import SystemMap

OUT = Path(__file__).with_suffix(".html")

m = SystemMap(title="sysatlas — read/write loops around the ontology")

m.add_component("User",            layer="inputs",   tech="human")
m.add_component("LLM",             layer="inputs",   tech="coding assistant")
m.add_component("Source code",     layer="inputs",   tech=".py files")

m.add_component("Builders",        layer="write",    tech="SystemMap · System · TreeMap")
m.add_component("Reflection",      layer="write",    tech="sysatlas.reflect()")

m.add_component("Ontology",        layer="ontology", tech="sysatlas._ontology")

m.add_component("Layout + Render", layer="read",     tech="_layout · _route · _render")

m.add_component("Diagrams",        layer="output",   tech="HTML · PNG")

# Forward write loop
m.connect("User",        "Builders",   label="writes")
m.connect("LLM",         "Builders",   label="generates")
m.connect("Builders",    "Ontology",   label="instantiates")

# Backward write loop
m.connect("LLM",         "Source code", label="generates")
m.connect("Source code", "Reflection",  label="parsed by")
m.connect("Reflection",  "Ontology",    label="instantiates")

# Read loop
m.connect("Ontology",        "Layout + Render", label="reads")
m.connect("Layout + Render", "Diagrams")

m.save(str(OUT))
print(f"[sysatlas] wrote {OUT}")
