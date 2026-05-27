"""Heuristic: top-level package segment → architectural layer name.

Used as a default when no hints file is provided. Overridable per-module
via sysatlas.yaml. The set of layer names matches what SystemMap expects.
"""
from __future__ import annotations


_LAYER_RULES: list[tuple[tuple[str, ...], str]] = [
    (("api", "web", "http", "rest", "edge", "gateway", "controllers", "handlers"), "edge"),
    (("ui", "frontend", "views", "templates", "client"), "edge"),
    (("services", "service", "domain", "core", "logic", "biz", "usecases"), "services"),
    (("db", "database", "storage", "persistence", "repo", "repositories", "models"), "data"),
    (("infra", "infrastructure", "platform", "config", "settings", "ops"), "infra"),
    (("vendor", "_vendor", "external", "thirdparty", "lib", "libs"), "external"),
]


def infer_layer(module_name: str) -> str:
    """Pick a layer for a dotted module name. Falls back to 'services'."""
    parts = [p.lower().lstrip("_") for p in module_name.split(".")]
    for keywords, layer in _LAYER_RULES:
        for p in parts:
            if p in keywords:
                return layer
    return "services"


def infer_group(module_name: str) -> str | None:
    """Return the second dotted segment (sub-package) as a group, if any.

    'sysatlas._ontology.architecture' → '_ontology'. Top-level modules
    ('sysatlas.system_map') return None — they sit at root, no group.
    """
    parts = module_name.split(".")
    if len(parts) < 3:
        return None
    return parts[1]
