"""Intended architecture, declared by people, and a check of the code against it.

The spec lives in the hints file under "architecture". It names components (as
module globs), the components each may depend on, and optionally an ordered list
of layers. `check_conformance` compares that plan with the real import graph.
"""
from __future__ import annotations

import fnmatch
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_EXAMPLES_PER_VIOLATION = 3


class SpecComponent(BaseModel):
    """A planned component: the modules it claims and the components it may depend on."""
    model_config = ConfigDict(extra="forbid")

    name: str
    modules: list[str]
    """Globs matched, case-sensitively, against the dotted module name and the path under the scan root. `*` also matches '.' and '/'."""
    depends_on: list[str] = Field(default_factory=list)
    """Names of the components this one may import. Anything else is a violation."""
    layer: str = ""
    """Layer name from `ArchitectureSpec.layers`; empty means unlayered."""


class ArchitectureSpec(BaseModel):
    """The planned architecture: optional layer order and the planned components."""
    model_config = ConfigDict(extra="forbid")

    layers: list[str] = Field(default_factory=list)
    """Layer names from top to bottom. A layer may depend on itself and on layers below it."""
    components: list[SpecComponent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> "ArchitectureSpec":
        if len(set(self.layers)) != len(self.layers):
            raise ValueError("architecture spec: layer names must be unique")
        names = [c.name for c in self.components]
        if len(set(names)) != len(names):
            raise ValueError("architecture spec: component names must be unique")
        known = set(names)
        for c in self.components:
            missing = sorted(set(c.depends_on) - known)
            if missing:
                raise ValueError(
                    f"architecture spec: component '{c.name}' depends on unknown {missing}"
                )
            if c.layer and c.layer not in self.layers:
                raise ValueError(
                    f"architecture spec: component '{c.name}' has layer '{c.layer}' "
                    f"which is not in layers {self.layers}"
                )
        return self


class SpecViolation(BaseModel):
    """A dependency the spec forbids, rolled up per pair of components."""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["dependency", "layer"]
    src: str
    dst: str
    count: int
    examples: list[str] = Field(default_factory=list)


class Conformance(BaseModel):
    """Result of comparing the declared architecture with the code."""
    model_config = ConfigDict(extra="forbid")

    ok: bool
    mapped_modules: int
    unmapped_modules: list[str] = Field(default_factory=list)
    """Modules that no spec component claims, sorted."""
    empty_components: list[str] = Field(default_factory=list)
    """Spec components that match no module, sorted."""
    violations: list[SpecViolation] = Field(default_factory=list)


def check_conformance(
    spec: ArchitectureSpec,
    modules: list[tuple[str, str]],
    edges: set[tuple[str, str]],
) -> Conformance:
    """Compare the spec with the code.

    `modules` is (dotted name, path under the scan root) per kept module and
    `edges` the internal import edges between dotted names. A module belongs to
    the first spec component, in declared order, whose glob matches it.
    """
    owner: dict[str, str] = {}
    for name, rel in sorted(modules):
        for comp in spec.components:
            if any(fnmatch.fnmatchcase(name, g) or fnmatch.fnmatchcase(rel, g) for g in comp.modules):
                owner[name] = comp.name
                break

    by_name = {c.name: c for c in spec.components}
    layer_index = {name: i for i, name in enumerate(spec.layers)}
    found: dict[tuple[str, str, str], list[str]] = {}
    for src, dst in sorted(edges):
        a, b = owner.get(src), owner.get(dst)
        if a is None or b is None or a == b:
            continue
        example = f"{src} -> {dst}"
        if b not in by_name[a].depends_on:
            found.setdefault(("dependency", a, b), []).append(example)
        la, lb = by_name[a].layer, by_name[b].layer
        if la and lb and layer_index[la] > layer_index[lb]:
            found.setdefault(("layer", a, b), []).append(example)

    violations = [
        SpecViolation(
            kind=kind, src=a, dst=b, count=len(ex), examples=ex[:_EXAMPLES_PER_VIOLATION]
        )
        for (kind, a, b), ex in sorted(found.items())
    ]
    claimed = set(owner.values())
    return Conformance(
        ok=not violations and len(owner) == len(modules),
        mapped_modules=len(owner),
        unmapped_modules=sorted(n for n, _ in modules if n not in owner),
        empty_components=sorted(c.name for c in spec.components if c.name not in claimed),
        violations=violations,
    )
