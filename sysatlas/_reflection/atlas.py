"""Deterministic "architecture atlas" model from a Reflection.

Same source tree -> byte-identical output. No timestamps, no absolute paths,
every list sorted with an explicit key. The atlas reuses the Reflection
keep / layer / group / display machinery so it never disagrees with the
diagrams that `to_system_map()` / `to_system()` produce.

Beyond the import digest it maps the architecture: components and their tiers,
entry points, external systems, data models, configuration, conformance with a
declared spec, and the human-written intent overlay. Rendering to Markdown
lives in atlas_render.py.
"""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from sysatlas._reflection.components import compute_components
from sysatlas._reflection.external import KINDS_AS_ADAPTER, classify_external
from sysatlas._reflection.intent import Intent, fingerprint, load_intent
from sysatlas._reflection.layers import layer_rank
from sysatlas._reflection.metrics import ROOT_GROUP, compute_metrics
from sysatlas._reflection.parser import ClassLink
from sysatlas._reflection.patterns import PatternCandidate, detect_patterns
from sysatlas._reflection.project import console_scripts
from sysatlas._reflection.spec import Conformance, check_conformance

if TYPE_CHECKING:
    from sysatlas._reflection.parser import Module
    from sysatlas._reflection.reflection import Reflection

_ROOT_GROUP = ROOT_GROUP
_SIZE_BUCKETS = ((20, "xs"), (75, "s"), (200, "m"), (500, "l"))
_HOTSPOT_LIMIT = 10


def _dedupe_by_name(modules: "list[Module]") -> "list[Module]":
    """Collapse modules that share a dotted name (e.g. Rust `main.rs` + `lib.rs`
    both mapping to `crate`), keeping the larger one so metrics stay coherent."""
    best: dict[str, Module] = {}
    for m in modules:
        cur = best.get(m.name)
        if cur is None or (m.loc, m.path) > (cur.loc, cur.path):
            best[m.name] = m
    return list(best.values())


def _size_bucket(loc: int) -> str:
    for ceiling, name in _SIZE_BUCKETS:
        if loc < ceiling:
            return name
    return "xl"


class AtlasModule(BaseModel):
    """One module with its metrics, component, role and architecture facts."""
    model_config = ConfigDict(extra="forbid")

    name: str
    display: str
    label: str
    """Short name for prose/tables — `display`, or a longer form when `display` collides."""
    group: str
    layer: str
    component: str
    """Name of the component this module belongs to."""
    role: str
    """entry-point, model, adapter, logic, or support."""
    rel_path: str
    purpose: str
    size: str
    loc: int
    classes: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    internal_deps: list[str] = Field(default_factory=list)
    fan_in: int
    fan_out: int
    unparsed: bool = False
    external: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    undocumented: list[str] = Field(default_factory=list)
    implements: list[ClassLink] = Field(default_factory=list)
    fluent_classes: list[str] = Field(default_factory=list)


class AtlasLayer(BaseModel):
    """A named layer and the modules placed in it."""
    model_config = ConfigDict(extra="forbid")

    name: str
    members: list[str] = Field(default_factory=list)


class AtlasCycle(BaseModel):
    """One import cycle: its members and the edges that close it."""
    model_config = ConfigDict(extra="forbid")

    members: list[str] = Field(default_factory=list)
    edges: list[str] = Field(default_factory=list)


class AtlasCrossPackage(BaseModel):
    """Imports from one package into another, rolled up with examples."""
    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str
    edges: int
    examples: list[str] = Field(default_factory=list)


class AtlasComponent(BaseModel):
    """A cluster of modules that acts as one architectural unit."""
    model_config = ConfigDict(extra="forbid")

    name: str
    tier: int
    """0 = nothing depends on it; higher = further down the dependency order."""
    layer: str
    roles: list[str] = Field(default_factory=list)
    """Role mix of the members, e.g. 'model×7', most common first."""
    modules: list[str] = Field(default_factory=list)
    """Member module labels, sorted."""
    module_count: int
    loc: int
    depends_on: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)
    """External systems this component talks to, sorted."""
    purpose: str = ""
    """From the intent overlay; empty when none is recorded."""
    patterns: list[str] = Field(default_factory=list)
    intent_state: Literal["none", "unverified", "current", "stale"] = "none"
    fingerprint: str
    """Digest of the members' public symbols; copy it into the intent entry."""


class AtlasComponentEdge(BaseModel):
    """Dependency of one component on another, with the module edges behind it."""
    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str
    edges: int
    examples: list[str] = Field(default_factory=list)


class AtlasEntryPoint(BaseModel):
    """A way the system is entered: main guard, script, route, CLI command or task."""
    model_config = ConfigDict(extra="forbid")

    module: str
    component: str
    kind: str
    """'main', 'script NAME', 'route GET /x', 'cli fn' or 'task fn'."""


class AtlasExternal(BaseModel):
    """An external system (database, API, queue, ...) and the components that use it."""
    model_config = ConfigDict(extra="forbid")

    kind: str
    system: str
    used_by: list[str] = Field(default_factory=list)
    """Component names, sorted."""


class AtlasModels(BaseModel):
    """Data-model classes that live in one component."""
    model_config = ConfigDict(extra="forbid")

    component: str
    models: list[str] = Field(default_factory=list)


class AtlasEnvVar(BaseModel):
    """An environment variable read with a literal key, and the modules that read it."""
    model_config = ConfigDict(extra="forbid")

    name: str
    modules: list[str] = Field(default_factory=list)


class AtlasPattern(BaseModel):
    """An architectural pattern recorded in the intent overlay."""
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    components: list[str] = Field(default_factory=list)


class AtlasUndocumented(BaseModel):
    """Public symbols of one module that have no docstring."""
    model_config = ConfigDict(extra="forbid")

    module: str
    symbols: list[str] = Field(default_factory=list)


class AtlasGaps(BaseModel):
    """What a person or an LLM still has to write down."""
    model_config = ConfigDict(extra="forbid")

    modules_without_doc: list[str] = Field(default_factory=list)
    undocumented_symbols: list[AtlasUndocumented] = Field(default_factory=list)
    components_without_intent: list[str] = Field(default_factory=list)
    stale_intent: list[str] = Field(default_factory=list)
    unknown_intent: list[str] = Field(default_factory=list)
    """Intent entries naming a component that no longer exists, including pattern references."""


class Atlas(BaseModel):
    """Structured backing model for the Markdown atlas. JSON via `model_dump_json()`."""
    model_config = ConfigDict(extra="forbid")

    title: str
    root: str
    language: str
    module_count: int
    unparsed_count: int
    edge_count: int
    package_count: int
    cycle_count: int
    truncated: bool
    max_modules: int
    summary: str = ""
    """System summary from the intent overlay."""
    components: list[AtlasComponent] = Field(default_factory=list)
    component_edges: list[AtlasComponentEdge] = Field(default_factory=list)
    entry_points: list[AtlasEntryPoint] = Field(default_factory=list)
    external_systems: list[AtlasExternal] = Field(default_factory=list)
    libraries: list[str] = Field(default_factory=list)
    """Other third-party packages that are not a known external system."""
    data_models: list[AtlasModels] = Field(default_factory=list)
    env_vars: list[AtlasEnvVar] = Field(default_factory=list)
    pattern_candidates: list[PatternCandidate] = Field(default_factory=list)
    """Patterns whose structural footprint was found; to be confirmed by reading the source."""
    patterns: list[AtlasPattern] = Field(default_factory=list)
    conformance: Conformance | None = None
    """Set only when the hints file declares an `architecture` spec."""
    gaps: AtlasGaps = Field(default_factory=AtlasGaps)
    layers: list[AtlasLayer] = Field(default_factory=list)
    modules: list[AtlasModule] = Field(default_factory=list)
    cross_package: list[AtlasCrossPackage] = Field(default_factory=list)
    cycles: list[AtlasCycle] = Field(default_factory=list)
    hotspots: list[str] = Field(default_factory=list)
    public_api: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        from sysatlas._reflection.atlas_render import render_markdown
        return render_markdown(self)


def build_atlas_model(
    reflection: "Reflection",
    title: str = "",
    *,
    max_modules: int = 80,
    intent: "str | Path | dict[str, Any] | Intent | None" = None,
) -> Atlas:
    """Build the structured Atlas from a Reflection (does not render Markdown)."""
    kept = _dedupe_by_name(reflection._kept_modules())
    root_path = Path(reflection.graph.root)
    root_name = root_path.name or str(root_path)
    language = "rust" if any(m.package == "crate" for m in kept) else "python"
    intent_model = load_intent(intent)

    metrics = compute_metrics(kept, reflection._group_for)
    mm = metrics.by_name()

    display_of = {m.name: reflection._display_name(m.name) for m in kept}
    label_of = _disambiguate(display_of)
    names = sorted(m.name for m in kept)
    edges = {(m.name, d) for m in kept for d in mm[m.name].internal_deps}
    cgraph = compute_components(
        names, edges, reflection._group_for, reflection._layer_for, lambda n: label_of[n]
    )
    scripts = console_scripts(root_path)

    modules: list[AtlasModule] = []
    for m in sorted(kept, key=lambda m: m.name):
        try:
            rel = Path(m.path).relative_to(root_path).as_posix()
        except ValueError:
            rel = Path(m.path).name
        node = mm[m.name]
        entries = sorted({*m.entry_points, *(f"script {s}" for s in scripts.get(m.name, []))})
        modules.append(
            AtlasModule(
                name=m.name,
                display=display_of[m.name],
                label=label_of[m.name],
                group=reflection._group_for(m.name) or _ROOT_GROUP,
                layer=reflection._layer_for(m.name),
                component=cgraph.owner[m.name],
                role=_role(m, entries),
                rel_path=rel,
                purpose=m.doc,
                size=_size_bucket(m.loc),
                loc=m.loc,
                classes=list(m.classes),
                functions=list(m.functions),
                internal_deps=node.internal_deps,
                fan_in=node.fan_in,
                fan_out=node.fan_out,
                unparsed=m.unparsed,
                external=list(m.external),
                entry_points=entries,
                models=list(m.models),
                env_vars=list(m.env_vars),
                undocumented=list(m.undocumented),
                implements=list(m.implements),
                fluent_classes=list(m.fluent_classes),
            )
        )

    layers = _build_layers(modules)
    cross = [
        AtlasCrossPackage(src=e.src, dst=e.dst, edges=e.count, examples=list(e.examples))
        for e in metrics.cross_package
    ]
    cycles = _build_cycles(
        metrics.cycles,
        {m.name: m.label for m in modules},
        {m.name: m.internal_deps for m in modules},
    )
    hotspots = [
        m.name
        for m in sorted(
            modules, key=lambda m: (-(m.fan_in + m.fan_out), m.name)
        )
        if m.fan_in + m.fan_out > 0
    ][:_HOTSPOT_LIMIT]

    components = _build_components(modules, cgraph, intent_model)
    systems, libraries = _build_externals(modules)
    conformance = None
    if reflection.hints.architecture is not None:
        conformance = check_conformance(
            reflection.hints.architecture, [(m.name, m.rel_path) for m in modules], edges
        )

    return Atlas(
        title=title or root_name,
        root=root_name,
        language=language,
        module_count=len(modules),
        unparsed_count=sum(1 for m in modules if m.unparsed),
        edge_count=metrics.edge_count,
        package_count=len({m.group for m in modules}),
        cycle_count=len(cycles),
        truncated=len(modules) > max_modules,
        max_modules=max_modules,
        summary=intent_model.summary if intent_model else "",
        components=components,
        component_edges=[
            AtlasComponentEdge(src=e.src, dst=e.dst, edges=e.count, examples=e.examples)
            for e in cgraph.edges
        ],
        entry_points=sorted(
            (
                AtlasEntryPoint(module=m.label, component=m.component, kind=k)
                for m in modules
                for k in m.entry_points
            ),
            key=lambda e: (e.kind, e.module),
        ),
        external_systems=systems,
        libraries=libraries,
        data_models=_build_data_models(modules),
        env_vars=_build_env_vars(modules),
        pattern_candidates=detect_patterns(modules, components, len(cycles)),
        patterns=[
            AtlasPattern(name=p.name, description=p.description, components=sorted(p.components))
            for p in sorted(intent_model.patterns, key=lambda p: p.name)
        ]
        if intent_model
        else [],
        conformance=conformance,
        gaps=_build_gaps(modules, components, intent_model),
        layers=layers,
        modules=modules,
        cross_package=cross,
        cycles=cycles,
        hotspots=hotspots,
        public_api=_public_api(root_path),
    )


def build_atlas(
    reflection: "Reflection",
    title: str = "",
    *,
    max_modules: int = 80,
    intent: "str | Path | dict[str, Any] | Intent | None" = None,
) -> str:
    """Build the Markdown atlas string from a Reflection."""
    return build_atlas_model(
        reflection, title, max_modules=max_modules, intent=intent
    ).to_markdown()


def _role(m: "Module", entries: list[str]) -> str:
    if entries:
        return "entry-point"
    if m.models and not m.functions and set(m.models) == set(m.classes):
        return "model"
    if any(classify_external(root)[0] in KINDS_AS_ADAPTER for root in m.external):
        return "adapter"
    if m.classes or m.functions:
        return "logic"
    return "support"


def _systems_of(roots: list[str]) -> list[str]:
    """Distinct external-system labels for a module's import roots, sorted."""
    return sorted(
        {label for kind, label in (classify_external(r) for r in roots) if kind != "library"}
    )


def _build_components(
    modules: list[AtlasModule], cgraph, intent: Intent | None
) -> list[AtlasComponent]:
    by_comp: dict[str, list[AtlasModule]] = {}
    for m in modules:
        by_comp.setdefault(m.component, []).append(m)
    out: list[AtlasComponent] = []
    for core in cgraph.components:
        members = sorted(by_comp[core.name], key=lambda m: m.name)
        layer_counts = Counter(m.layer for m in members)
        layer = sorted(layer_counts, key=lambda name: (-layer_counts[name], name))[0]
        role_counts = Counter(m.role for m in members)
        roles = [
            f"{r}×{role_counts[r]}"
            for r in sorted(role_counts, key=lambda r: (-role_counts[r], r))
        ]
        fp = fingerprint([(m.name, [*m.classes, *m.functions]) for m in members])
        entry = intent.components.get(core.name) if intent else None
        if entry is None:
            state = "none"
        elif not entry.fingerprint:
            state = "unverified"
        else:
            state = "current" if entry.fingerprint == fp else "stale"
        out.append(
            AtlasComponent(
                name=core.name,
                tier=core.tier,
                layer=layer,
                roles=roles,
                modules=[m.label for m in members],
                module_count=len(members),
                loc=sum(m.loc for m in members),
                depends_on=core.depends_on,
                dependents=core.dependents,
                external=sorted({s for m in members for s in _systems_of(m.external)}),
                purpose=entry.purpose if entry else "",
                patterns=sorted(entry.patterns) if entry else [],
                intent_state=state,
                fingerprint=fp,
            )
        )
    return out


def _build_externals(modules: list[AtlasModule]) -> tuple[list[AtlasExternal], list[str]]:
    used: dict[tuple[str, str], set[str]] = {}
    libraries: set[str] = set()
    for m in modules:
        for root in m.external:
            kind, label = classify_external(root)
            if kind == "library":
                libraries.add(root)
            else:
                used.setdefault((kind, label), set()).add(m.component)
    systems = [
        AtlasExternal(kind=k, system=s, used_by=sorted(comps))
        for (k, s), comps in sorted(used.items())
    ]
    return systems, sorted(libraries)


def _build_data_models(modules: list[AtlasModule]) -> list[AtlasModels]:
    by_comp: dict[str, set[str]] = {}
    for m in modules:
        if m.models:
            by_comp.setdefault(m.component, set()).update(m.models)
    return [AtlasModels(component=c, models=sorted(ms)) for c, ms in sorted(by_comp.items())]


def _build_env_vars(modules: list[AtlasModule]) -> list[AtlasEnvVar]:
    users: dict[str, set[str]] = {}
    for m in modules:
        for var in m.env_vars:
            users.setdefault(var, set()).add(m.label)
    return [AtlasEnvVar(name=v, modules=sorted(ms)) for v, ms in sorted(users.items())]


def _build_gaps(
    modules: list[AtlasModule], components: list[AtlasComponent], intent: Intent | None
) -> AtlasGaps:
    known = {c.name for c in components}
    return AtlasGaps(
        modules_without_doc=sorted(m.label for m in modules if not m.purpose and not m.unparsed),
        undocumented_symbols=[
            AtlasUndocumented(module=m.label, symbols=list(m.undocumented))
            for m in sorted(modules, key=lambda m: m.label)
            if m.undocumented
        ],
        components_without_intent=sorted(c.name for c in components if c.intent_state == "none"),
        stale_intent=sorted(c.name for c in components if c.intent_state == "stale"),
        unknown_intent=sorted(
            [n for n in (intent.components if intent else {}) if n not in known]
            + [
                f"pattern '{p.name}' names {c}"
                for p in (intent.patterns if intent else [])
                for c in sorted(set(p.components) - known)
            ]
        ),
    )


def _disambiguate(display_of: dict[str, str]) -> dict[str, str]:
    """Map dotted name -> a label that is unique across the kept set.

    Uses the plain display name where it is unique; otherwise the dotted name
    with the shared root package stripped, falling back to the full dotted name.
    """
    clashed = {d for d, n in Counter(display_of.values()).items() if n > 1}
    if not clashed:
        return dict(display_of)
    out: dict[str, str] = {}
    for name, display in display_of.items():
        if display not in clashed:
            out[name] = display
            continue
        stripped = ".".join(name.split(".")[1:]) or name
        out[name] = stripped
    if len(set(out.values())) < len(out):
        for name, display in display_of.items():
            if display in clashed:
                out[name] = name
    return out


def _build_layers(modules: list[AtlasModule]) -> list[AtlasLayer]:
    by_layer: dict[str, list[str]] = {}
    for m in modules:
        by_layer.setdefault(m.layer, []).append(m.label)
    ordered = sorted(by_layer, key=lambda name: (layer_rank(name), name))
    return [AtlasLayer(name=name, members=sorted(by_layer[name])) for name in ordered]


def _build_cycles(
    raw_cycles: list[list[str]],
    display: dict[str, str],
    deps: dict[str, list[str]],
) -> list[AtlasCycle]:
    out: list[AtlasCycle] = []
    for members in raw_cycles:
        member_set = set(members)
        edges = sorted(
            f"{display.get(a, a)} -> {display.get(b, b)}"
            for a in members
            for b in deps.get(a, [])
            if b in member_set
        )
        out.append(
            AtlasCycle(
                members=[display.get(x, x) for x in members],
                edges=edges,
            )
        )
    return out


def _public_api(root_path: Path) -> list[str]:
    init = root_path / "__init__.py"
    if not init.is_file():
        return []
    try:
        tree = ast.parse(init.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                continue
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            if not (isinstance(node.target, ast.Name) and node.target.id == "__all__"):
                continue
            value = node.value
        else:
            continue
        if isinstance(value, (ast.List, ast.Tuple)):
            return [
                el.value
                for el in value.elts
                if isinstance(el, ast.Constant) and isinstance(el.value, str)
            ]
    return []
