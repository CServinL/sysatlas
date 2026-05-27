"""Conceptual view: sysatlas as read/write loops around its ontology.

Hand-authored (forward flow), rendered with the hub-and-spoke strategy.
Tells the story of what sysatlas *is*, not what its files import.

Layout regions (selected by Component.layer):
  - interfaces (top)  : User, LLM
  - write      (left) : Builders, Reflection — write into the hub
  - hub        (centre): Ontology
  - read       (right): Layout + Render     — read from the hub
  - external   (bottom): Source code, Diagrams — the storage the system
                          reads from / writes back to.

Run: python docs/reflection/loops.py
"""
from pathlib import Path

from sysatlas import SystemMap

OUT = Path(__file__).with_suffix(".html")

m = SystemMap(strategy="hub",
              title="sysatlas — read/write loops around the ontology")

m.add_component("User",            layer="interfaces", tech="human")
m.add_component("LLM",             layer="interfaces", tech="coding assistant")

m.add_component("Builders",        layer="write",      tech="SystemMap · System · TreeMap")
m.add_component("Reflection",      layer="write",      tech="sysatlas.reflect()")

m.add_component("Ontology",        layer="hub",        tech="sysatlas._ontology")

m.add_component("Layout + Render", layer="read",       tech="_layout · _route · _render")

m.add_component("Source code",     layer="external",   tech=".py files")
m.add_component("Diagrams",        layer="external",   tech="HTML · PNG")

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
m.connect("Layout + Render", "Diagrams",        label="renders")

m.save(str(OUT))
print(f"[sysatlas] wrote {OUT}")
