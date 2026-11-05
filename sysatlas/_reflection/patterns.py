"""Architectural pattern candidates found from structure alone.

Each detector looks for the structural footprint of a pattern and reports it with
the evidence that triggered it. These are candidates, not verdicts: a person or
the sysatlas-document skill reads the source and decides. Patterns whose
footprint is not structural (state machine, dependency injection, middleware
chain) are not detected here.

Pure and deterministic: every output list is sorted with an explicit key.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from sysatlas._reflection.external import classify_external

if TYPE_CHECKING:
    from sysatlas._reflection.atlas import AtlasComponent, AtlasModule

MIN_TIERS = 3
MIN_PIPELINE_STAGES = 3
MIN_IMPLEMENTATIONS = 2
FACADE_MIN_FAN_IN = 3
FACADE_MIN_FAN_OUT = 3
FACADE_LOC_PER_OUT = 40
REGISTRY_MIN_FAN_IN = 2
MIN_COMMAND_ENTRIES = 2
_EVIDENCE_ITEMS = 5
_IMPLEMENTERS_SHOWN = 8
_PIPELINES_SHOWN = 3
_STORE_SUFFIXES = ("Repository", "Repo", "Store", "DAO", "Dao")
_PUBLISH = frozenset({"publish", "publish_event"})
_SUBSCRIBE = frozenset({"subscribe", "add_listener", "add_subscriber"})
_NOT_A_BUS = frozenset({"smtplib"})
ORDER = (
    "Layered",
    "Pipeline",
    "Ports and adapters",
    "Strategy",
    "Facade",
    "Fluent builder",
    "Plugin registry",
    "Repository",
    "Event-driven",
    "Client and server",
    "Command and task queue",
)
"""Fixed output order, matching the checklist in the sysatlas-document skill."""


class PatternCandidate(BaseModel):
    """A pattern whose structural footprint was found, with the evidence."""
    model_config = ConfigDict(extra="forbid")

    name: str
    evidence: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    """Components involved, sorted. Empty when the evidence spans the whole system."""


def detect_patterns(
    modules: "list[AtlasModule]",
    components: "list[AtlasComponent]",
    cycle_count: int,
) -> list[PatternCandidate]:
    """Run every detector over the atlas modules and return the candidates in `ORDER`."""
    by_name = {m.name: m for m in modules}
    found = [
        _layered(components, cycle_count),
        _pipeline(modules),
        *_interfaces(modules, by_name),
        _facade(modules),
        _fluent_builder(modules),
        _plugin_registry(modules),
        _repository(modules),
        _event_driven(modules),
        _client_server(modules),
        _commands(modules),
    ]
    rank = {name: i for i, name in enumerate(ORDER)}
    return sorted((c for c in found if c), key=lambda c: rank[c.name])


def _capped(items: list[str]) -> list[str]:
    if len(items) <= _EVIDENCE_ITEMS:
        return items
    return [*items[:_EVIDENCE_ITEMS], f"… +{len(items) - _EVIDENCE_ITEMS} more"]


def _comps(modules: "list[AtlasModule]") -> list[str]:
    return sorted({m.component for m in modules})


def _layered(components: "list[AtlasComponent]", cycle_count: int) -> PatternCandidate | None:
    tiers = max((c.tier for c in components), default=-1) + 1
    if tiers < MIN_TIERS:
        return None
    evidence = [f"{tiers} dependency tiers over {len(components)} components"]
    evidence.append(
        f"{cycle_count} import cycle(s) merged into components, which weakens the layering"
        if cycle_count
        else "no import cycles"
    )
    return PatternCandidate(name="Layered", evidence=evidence)


def _pipeline(modules: "list[AtlasModule]") -> PatternCandidate | None:
    """Chains of modules where each stage has one dependency and the next stage one dependent.

    Runs on modules, not components: single-caller helpers are merged into one
    component, which would hide exactly this shape.
    """
    by_name = {m.name: m for m in modules}
    dependents: dict[str, list[str]] = {m.name: [] for m in modules}
    for m in modules:
        for dep in m.internal_deps:
            if dep in dependents:
                dependents[dep].append(m.name)

    def deps(name: str) -> list[str]:
        return [d for d in by_name[name].internal_deps if d in by_name]

    chains: list[list[str]] = []
    for m in sorted(modules, key=lambda m: m.name):
        preds = dependents[m.name]
        if len(preds) == 1 and len(deps(preds[0])) == 1:
            continue  # continuation of a chain that starts earlier
        chain = [m.name]
        seen = {m.name}
        cur = m.name
        while len(deps(cur)) == 1:
            nxt = deps(cur)[0]
            if len(dependents[nxt]) != 1 or nxt in seen:
                break
            chain.append(nxt)
            seen.add(nxt)
            cur = nxt
        if len(chain) >= MIN_PIPELINE_STAGES:
            chains.append(chain)
    if not chains:
        return None
    chains.sort(key=lambda ch: (-len(ch), [by_name[n].label for n in ch]))
    shown = chains[:_PIPELINES_SHOWN]
    return PatternCandidate(
        name="Pipeline",
        evidence=[" -> ".join(by_name[n].label for n in ch) for ch in shown]
        + ([f"… +{len(chains) - len(shown)} more chains"] if len(chains) > len(shown) else []),
        components=_comps([by_name[n] for ch in shown for n in ch]),
    )


def _interfaces(
    modules: "list[AtlasModule]", by_name: "dict[str, AtlasModule]"
) -> list[PatternCandidate]:
    impls: dict[tuple[str, str], list["AtlasModule"]] = {}
    names: dict[tuple[str, str], list[str]] = {}
    for m in modules:
        for link in m.implements:
            key = (link.base_module, link.base)
            impls.setdefault(key, []).append(m)
            names.setdefault(key, []).append(f"{link.cls} ({m.label})")
    adapters: list[str] = []
    strategies: list[str] = []
    adapter_comps: set[str] = set()
    strategy_comps: set[str] = set()
    for key in sorted(impls):
        group = impls[key]
        if len(group) < MIN_IMPLEMENTATIONS:
            continue
        base_mod = by_name.get(key[0])
        label = f"{key[1]} ({base_mod.label if base_mod else key[0]})"
        shown = sorted(names[key])
        more = f", … +{len(shown) - _IMPLEMENTERS_SHOWN}" if len(shown) > _IMPLEMENTERS_SHOWN else ""
        line = f"{label}: {', '.join(shown[:_IMPLEMENTERS_SHOWN])}{more}"
        touching = {m.name for m in group if _systems(m)}
        core_clean = base_mod is not None and not _systems(base_mod)
        comps = {m.component for m in group} | ({base_mod.component} if base_mod else set())
        if core_clean and len(touching) >= MIN_IMPLEMENTATIONS:  # distinct modules
            adapters.append(line + " — implementations import external systems")
            adapter_comps |= comps
        else:
            strategies.append(line)
            strategy_comps |= comps
    out = []
    if adapters:
        out.append(
            PatternCandidate(
                name="Ports and adapters", evidence=_capped(adapters), components=sorted(adapter_comps)
            )
        )
    if strategies:
        out.append(
            PatternCandidate(
                name="Strategy", evidence=_capped(strategies), components=sorted(strategy_comps)
            )
        )
    return out


def _systems(m: "AtlasModule") -> list[str]:
    return sorted({lbl for kind, lbl in (classify_external(r) for r in m.external) if kind != "library"})


def _facade(modules: "list[AtlasModule]") -> PatternCandidate | None:
    hits = sorted(
        (
            m for m in modules
            if m.role != "entry-point"
            and m.fan_in >= FACADE_MIN_FAN_IN
            and m.fan_out >= FACADE_MIN_FAN_OUT
            and m.loc <= FACADE_LOC_PER_OUT * m.fan_out
        ),
        key=lambda m: (-(m.fan_in + m.fan_out), m.name),
    )
    if not hits:
        return None
    return PatternCandidate(
        name="Facade",
        evidence=_capped([f"{m.label}: fan-in {m.fan_in}, fan-out {m.fan_out}, {m.loc} loc" for m in hits]),
        components=_comps(hits),
    )


def _fluent_builder(modules: "list[AtlasModule]") -> PatternCandidate | None:
    hits = [(c, m) for m in modules for c in m.fluent_classes]
    if not hits:
        return None
    hits.sort(key=lambda h: (h[1].name, h[0]))
    return PatternCandidate(
        name="Fluent builder",
        evidence=_capped([f"{c} ({m.label})" for c, m in hits]),
        components=_comps([m for _, m in hits]),
    )


def _plugin_registry(modules: "list[AtlasModule]") -> PatternCandidate | None:
    hits = sorted(
        (
            (fn, m) for m in modules for fn in m.functions
            if fn.startswith("register") and m.fan_in >= REGISTRY_MIN_FAN_IN
        ),
        key=lambda h: (h[1].name, h[0]),
    )
    if not hits:
        return None
    return PatternCandidate(
        name="Plugin registry",
        evidence=_capped([f"{fn}() in {m.label}, imported by {m.fan_in} modules" for fn, m in hits]),
        components=_comps([m for _, m in hits]),
    )


def _repository(modules: "list[AtlasModule]") -> PatternCandidate | None:
    hits = []
    for m in modules:
        stores = sorted(
            lbl for kind, lbl in (classify_external(r) for r in m.external) if kind == "datastore"
        )
        if not stores:
            continue
        hits += [(c, m, stores[0]) for c in m.classes if c.endswith(_STORE_SUFFIXES)]
    if not hits:
        return None
    hits.sort(key=lambda h: (h[1].name, h[0]))
    return PatternCandidate(
        name="Repository",
        evidence=_capped([f"{c} ({m.label}) over {system}" for c, m, system in hits]),
        components=_comps([m for _, m, _ in hits]),
    )


def _event_driven(modules: "list[AtlasModule]") -> PatternCandidate | None:
    evidence: list[str] = []
    hit: list["AtlasModule"] = []
    for m in modules:
        fns = set(m.functions)
        if fns & _PUBLISH and fns & _SUBSCRIBE:
            evidence.append(
                f"{m.label}: functions {', '.join(sorted(fns & _PUBLISH))} / "
                f"{', '.join(sorted(fns & _SUBSCRIBE))} (names only)"
            )
            hit.append(m)
        queues = sorted(
            r for r in m.external if classify_external(r)[0] == "queue" and r not in _NOT_A_BUS
        )
        if queues:
            evidence.append(f"{m.label}: imports {', '.join(queues)}")
            hit.append(m)
    if not evidence:
        return None
    return PatternCandidate(name="Event-driven", evidence=_capped(sorted(evidence)), components=_comps(hit))


def _client_server(modules: "list[AtlasModule]") -> PatternCandidate | None:
    routes = [(e, m) for m in modules for e in m.entry_points if e.startswith("route ")]
    if not routes:
        return None
    evidence = [f"{len(routes)} routes in {len({m.component for _, m in routes})} component(s)"]
    clients = [m for m in modules if any(classify_external(r)[0] == "http-client" for r in m.external)]
    if clients:
        evidence.append(f"outbound HTTP from {len({m.component for m in clients})} component(s)")
    return PatternCandidate(
        name="Client and server", evidence=evidence, components=_comps([m for _, m in routes])
    )


def _commands(modules: "list[AtlasModule]") -> PatternCandidate | None:
    kinds = {"cli ": 0, "task ": 0, "script ": 0}
    hit: list["AtlasModule"] = []
    for m in modules:
        for e in m.entry_points:
            for prefix in kinds:
                if e.startswith(prefix):
                    kinds[prefix] += 1
                    hit.append(m)
    total = sum(kinds.values())
    if total < MIN_COMMAND_ENTRIES:
        return None
    parts = [f"{n} {prefix.strip()} entr{'y' if n == 1 else 'ies'}" for prefix, n in kinds.items() if n]
    return PatternCandidate(name="Command and task queue", evidence=parts, components=_comps(hit))
