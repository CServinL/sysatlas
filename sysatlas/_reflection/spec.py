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
    """Declaration order is precedence: a module belongs to the first component whose glob matches it."""

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
    """Spec components whose globs match no module, sorted."""
    shadowed_components: list[str] = Field(default_factory=list)
    """Spec components whose globs match modules, all of which an earlier component already owns, sorted."""
    ambiguous_modules: list[str] = Field(default_factory=list)
    """Modules matched by more than one spec component (the first one owns it), sorted. Informational."""
    violations: list[SpecViolation] = Field(default_factory=list)


def matches_any_glob(name: str, rel_path: str, globs: list[str]) -> bool:
    """True when a dotted module name or its path under the scan root matches any glob (case-sensitive)."""
    return any(fnmatch.fnmatchcase(name, g) or fnmatch.fnmatchcase(rel_path, g) for g in globs)


def check_conformance(
    spec: ArchitectureSpec,
    modules: list[tuple[str, str]],
    edges: set[tuple[str, str]],
) -> Conformance:
    """Compare the spec with the code.

    `modules` is (dotted name, path under the scan root) per kept module and
    `edges` the internal import edges between dotted names. A module belongs to
    the first spec component, in declared order, whose glob matches it; modules
    that match several are listed as ambiguous.
    """
    owner: dict[str, str] = {}
    ambiguous: list[str] = []
    matched: set[str] = set()
    for name, rel in sorted(modules):
        matching = [c.name for c in spec.components if matches_any_glob(name, rel, c.modules)]
        matched.update(matching)
        if matching:
            owner[name] = matching[0]
        if len(matching) > 1:
            ambiguous.append(name)

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
    unmapped = sorted(n for n, _ in modules if n not in owner)
    empty = sorted(c.name for c in spec.components if c.name not in matched)
    shadowed = sorted(c.name for c in spec.components if c.name in matched and c.name not in claimed)
    return Conformance(
        ok=not (violations or unmapped or empty or shadowed),
        mapped_modules=len(owner),
        unmapped_modules=unmapped,
        empty_components=empty,
        shadowed_components=shadowed,
        ambiguous_modules=sorted(ambiguous),
        violations=violations,
    )
