"""Merge a user-authored 'annotation overlay' SystemMap onto reflected structure.

Goal: reflected diagram carries real structure; overlay adds intent
(qualities, label/tech overrides, traces, viewpoints). Components in the
overlay that don't match anything reflected stay visible as user-asserted
stubs so drift between intent and reality is obvious.
"""
from __future__ import annotations

from sysatlas._ontology.architecture import Component, Layer
from sysatlas.system_map import SystemMap


def merge_overlay(reflected: SystemMap, overlay: SystemMap) -> SystemMap:
    """Merge overlay's annotations onto reflected. Returns a new SystemMap.

    For each overlay component matching a reflected component (by name):
      - qualities are unioned
      - label/tech from overlay win if set
      - group from overlay wins if set
    For overlay components with no reflected match:
      - added as is_stub=True with defined_in='user-asserted', layer 'external'
    Overlay connections are added if both endpoints exist after merge.
    """
    out = SystemMap(title=reflected.diagram.title or overlay.diagram.title)
    out._diagram.strategy = reflected.diagram.strategy

    for layer in reflected.diagram.layers:
        out._diagram.layers.append(layer.model_copy())
    for name, group in reflected.diagram.groups.items():
        out._diagram.groups[name] = group.model_copy()
    for name, group in overlay.diagram.groups.items():
        if name not in out._diagram.groups:
            out._diagram.groups[name] = group.model_copy()

    for name, comp in reflected.diagram.components.items():
        out._diagram.components[name] = comp.model_copy(deep=True)

    for name, ov in overlay.diagram.components.items():
        if name in out._diagram.components:
            base = out._diagram.components[name]
            merged_qualities = list(base.qualities) + [
                q for q in ov.qualities if q not in base.qualities
            ]
            out._diagram.components[name] = base.model_copy(update={
                "qualities": merged_qualities,
                "label": ov.label or base.label,
                "tech": ov.tech or base.tech,
                "group": ov.group or base.group,
            })
        else:
            out._diagram.components[name] = Component(
                **{
                    **ov.model_dump(),
                    "is_stub": True,
                    "defined_in": "user-asserted",
                    "layer": ov.layer or "external",
                }
            )

    declared_layers = {layer.name for layer in out._diagram.layers}
    for comp in out._diagram.components.values():
        if comp.layer and comp.layer not in declared_layers:
            out._diagram.layers.append(Layer(name=comp.layer))
            declared_layers.add(comp.layer)

    existing_edges = {(c.source, c.target) for c in reflected.diagram.connections}
    for c in reflected.diagram.connections:
        out._diagram.connections.append(c.model_copy(deep=True))
    for c in overlay.diagram.connections:
        if c.source not in out._diagram.components or c.target not in out._diagram.components:
            continue
        if (c.source, c.target) in existing_edges:
            continue
        out._diagram.connections.append(c.model_copy(deep=True))

    return out
