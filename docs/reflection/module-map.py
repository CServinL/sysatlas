"""sysatlas self-portrait: one HTML, all views.

Views included:
  conceptual  — hand-authored hub: what sysatlas *is*
  root        — module-level: builders + pipeline (diagram-specific internals excluded)
  _ontology   — module-level: ontology schemas
  _reflection — module-level: reflection sub-package
  rust        — prisma-desktop Rust crate (skipped if not yet scaffolded)

Run: python docs/reflection/module-map.py
Requires reflect-rust extra for the Rust view:
  pip install 'sysatlas[reflect-rust]'
"""
from pathlib import Path

import sysatlas
from sysatlas import System, SystemMap

REPO   = Path(__file__).resolve().parents[2]
SOURCE = REPO / "sysatlas"
CRATE  = Path.home() / "Repos" / "CServinL" / "prisma-desktop"
OUT    = Path(__file__).with_suffix(".html")

# ── Python reflection (3 views: root, _ontology, _reflection) ────────────────
r = sysatlas.reflect(SOURCE)
# Exclude diagram-specific layout/render internals — they add noise to the root
# view without adding architectural insight (their story is told by builders).
r.exclude(
    "*/_bpmn_layout.py", "*/_bpmn_render.py",
    "*/_sequence_layout.py", "*/_sequence_render.py",
    "*/_tree_layout.py", "*/_tree_render.py",
)
s = r.to_system(title="sysatlas — full map")

# ── Conceptual view (forward flow, hand-authored) ────────────────────────────
s.viewpoint("conceptual", model_kinds=["architecture"])
loops = s.architecture_model("conceptual")
loops.diagram.strategy = "hub"

loops.add_component("User",            layer="interfaces", tech="human")
loops.add_component("LLM",             layer="interfaces", tech="coding assistant")
loops.add_component("Builders",        layer="write",      tech="SystemMap · System · TreeMap")
loops.add_component("Reflection",      layer="write",      tech="sysatlas.reflect()")
loops.add_component("Ontology",        layer="hub",        tech="sysatlas._ontology")
loops.add_component("Layout + Render", layer="read",       tech="_layout · _route · _render")
loops.add_component("Source code",     layer="external",   tech=".py / .rs files")
loops.add_component("Diagrams",        layer="external",   tech="HTML · PNG")

loops.connect("User",        "Builders",        label="writes")
loops.connect("LLM",         "Builders",        label="generates")
loops.connect("Builders",    "Ontology",        label="instantiates")
loops.connect("LLM",         "Source code",     label="generates")
loops.connect("Source code", "Reflection",      label="parsed by")
loops.connect("Reflection",  "Ontology",        label="instantiates")
loops.connect("Ontology",    "Layout + Render", label="reads")
loops.connect("Layout + Render", "Diagrams",    label="renders")

s.view("conceptual-view", viewpoint="conceptual", models=["conceptual"])

# ── Rust view ────────────────────────────────────────────────────────────────
# Shows prisma-desktop when it has enough modules; falls back to a placeholder
# sketch of the planned architecture until the crate grows.
rs_files = list(CRATE.rglob("*.rs")) if CRATE.exists() else []
_rust_has_content = False
if rs_files:
    try:
        r_rust = sysatlas.reflect_rust(CRATE)
        rust_mods = r_rust.graph.modules
        in_tree = {m.name for m in rust_mods}
        has_edges = any(m.imports for m in rust_mods)
        if has_edges:
            s.viewpoint("rust-modules", model_kinds=["architecture"])
            rust_view = s.architecture_model("rust")
            for mod in rust_mods:
                rust_view.add_component(mod.name.split(".")[-1] or mod.name, tech=mod.name)
            for mod in rust_mods:
                src = mod.name.split(".")[-1] or mod.name
                for imp in mod.imports:
                    tgt = imp.split(".")[-1] or imp
                    rust_view.connect(src, tgt)
            s.view("rust-view", viewpoint="rust-modules", models=["rust"])
            _rust_has_content = True
    except ImportError:
        print("[sysatlas] Rust view skipped — install 'sysatlas[reflect-rust]'")

if not _rust_has_content:
    # Placeholder: planned prisma-desktop architecture until crate grows
    s.viewpoint("rust-planned", model_kinds=["architecture"])
    rust_sketch = s.architecture_model("rust-planned")
    rust_sketch.group("tauri-backend", label="Rust / Tauri")
    rust_sketch.group("python-sidecar", label="Python sidecar")
    rust_sketch.add_component("main",        layer="edge",     group="tauri-backend")
    rust_sketch.add_component("commands",    layer="services", group="tauri-backend")
    rust_sketch.add_component("ipc",         layer="infra",    group="tauri-backend")
    rust_sketch.add_component("zotero",      layer="services", group="python-sidecar")
    rust_sketch.add_component("ollama",      layer="services", group="python-sidecar")
    rust_sketch.add_component("graphify",    layer="services", group="python-sidecar")
    rust_sketch.add_component("prisma-core", layer="data",     group="python-sidecar")
    rust_sketch.connect("main",     "commands", label="invoke")
    rust_sketch.connect("commands", "ipc",      label="dispatch")
    rust_sketch.connect("ipc",      "zotero")
    rust_sketch.connect("ipc",      "ollama")
    rust_sketch.connect("ipc",      "graphify")
    rust_sketch.connect("ipc",      "prisma-core")
    s.view("rust-planned-view", viewpoint="rust-planned", models=["rust-planned"])

s.save(str(OUT))
print(f"[sysatlas] wrote {OUT}")
