"""Decide whether an import target lives inside the scanned tree."""
from __future__ import annotations


def resolve_import(target: str, from_module: str, in_tree: set[str]) -> str | None:
    """Return the in-tree module name an import resolves to, or None if external.

    'from sysatlas._ontology.architecture import Component' yields target
    'sysatlas._ontology.architecture.Component' AND 'sysatlas._ontology.architecture'.
    The class name won't be in in_tree, but the module will — we walk up dotted
    segments until we find a match.
    """
    if not target:
        return None
    parts = target.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in in_tree and candidate != from_module:
            return candidate
    return None
