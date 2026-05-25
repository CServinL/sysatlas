"""Top-level fluent builder for a multi-view sysatlas project.

A `System` is a thin builder over an ISO 42010 `ArchitectureDescription`.
It composes multiple per-diagram-type sub-builders (today: `SystemMap`
for architecture diagrams) plus the meta-layer (stakeholders, concerns,
viewpoints, views, trace links).

The `.description` property returns the validated Pydantic AD.
"""
from __future__ import annotations

import os

from sysatlas._ontology.iso42010 import (
    ArchitectureDescription,
    Concern,
    Stakeholder,
    View,
    Viewpoint,
)
from sysatlas._ontology.trace import EntityRef, TraceLink, TraceLinkKind
from sysatlas._render import copy_local_viewer, render_collection
from sysatlas.system_map import SystemMap


class System:
    """Fluent builder for a multi-view ISO 42010 Architecture Description."""

    def __init__(self, title: str = "") -> None:
        self._title = title
        self._stakeholders: dict[str, Stakeholder] = {}
        self._concerns: dict[str, Concern] = {}
        self._viewpoints: dict[str, Viewpoint] = {}
        self._views: dict[str, View] = {}
        self._architecture_models: dict[str, SystemMap] = {}
        self._traces: list[TraceLink] = []

    # ── meta layer ─────────────────────────────────────────────────────────

    def stakeholder(self, name: str, *, role: str | None = None,
                    description: str | None = None) -> "System":
        self._stakeholders[name] = Stakeholder(name=name, role=role, description=description)
        return self

    def concern(self, name: str, *, stakeholders: list[str] | None = None,
                description: str | None = None) -> "System":
        self._concerns[name] = Concern(
            name=name,
            stakeholders=stakeholders or [],
            description=description,
        )
        return self

    def viewpoint(self, name: str, *, concerns: list[str] | None = None,
                  model_kinds: list[str] | None = None,
                  conventions: str | None = None,
                  description: str | None = None) -> "System":
        self._viewpoints[name] = Viewpoint(
            name=name,
            concerns=concerns or [],
            model_kinds=model_kinds or [],
            conventions=conventions,
            description=description,
        )
        return self

    def view(self, name: str, *, viewpoint: str, models: list[str],
             description: str | None = None) -> "System":
        self._views[name] = View(
            name=name,
            viewpoint=viewpoint,
            models=models,
            description=description,
        )
        return self

    # ── model builders ─────────────────────────────────────────────────────

    def architecture_model(self, name: str, *, title: str | None = None) -> SystemMap:
        """Create (or return) a `SystemMap` for an architecture diagram,
        registered as a model in this System under `name`."""
        if name in self._architecture_models:
            return self._architecture_models[name]
        sm = SystemMap(title=title or name)
        self._architecture_models[name] = sm
        return sm

    # ── trace links ────────────────────────────────────────────────────────

    def trace(self, source: str, target: str, *,
              kind: TraceLinkKind = "depends_on",
              note: str | None = None) -> "System":
        """Add a trace link. `source` and `target` are `'model#entity'` strings."""
        s_model, s_entity = self._parse_ref(source)
        t_model, t_entity = self._parse_ref(target)
        self._traces.append(TraceLink(
            source=EntityRef(model=s_model, entity=s_entity),
            target=EntityRef(model=t_model, entity=t_entity),
            kind=kind,
            note=note,
        ))
        return self

    @staticmethod
    def _parse_ref(ref: str) -> tuple[str, str]:
        if "#" not in ref:
            raise ValueError(f"trace ref must be 'model#entity', got {ref!r}")
        m, e = ref.split("#", 1)
        return m, e

    # ── introspection ──────────────────────────────────────────────────────

    @property
    def description(self) -> ArchitectureDescription:
        """Return the validated Pydantic Architecture Description."""
        models_typed = {n: sm.diagram for n, sm in self._architecture_models.items()}
        return ArchitectureDescription(
            title=self._title,
            stakeholders=self._stakeholders,
            concerns=self._concerns,
            viewpoints=self._viewpoints,
            views=self._views,
            models=models_typed,
        )

    @property
    def traces(self) -> list[TraceLink]:
        return list(self._traces)

    # ── rendering ──────────────────────────────────────────────────────────

    def save(self, path: str, viewer: str = "cdn") -> None:
        """Render the System as a multi-tab HTML.

        Each declared View becomes a tab. Views that reference architecture
        models are rendered via the existing SystemMap pipeline; other model
        kinds are not renderable yet and are skipped (with a warning).

        Cross-view references (connections to components defined in another
        view's model) are auto-added as stubs in the current view.
        """
        # Trigger AD validation up-front.
        _ = self.description

        # Index: which view defines each component?
        component_view: dict[str, str] = {}
        for view_name, view in self._views.items():
            for model_name in view.models:
                m = self._architecture_models.get(model_name)
                if m is None:
                    continue
                for comp_name in m.diagram.components:
                    if not m.diagram.components[comp_name].is_stub:
                        component_view.setdefault(comp_name, view_name)

        # One XML per view (currently: pick the first architecture model the view contains).
        xmls: dict[str, str] = {}
        for view_name, view in self._views.items():
            primary = None
            for model_name in view.models:
                if model_name in self._architecture_models:
                    primary = self._architecture_models[model_name]
                    break
            if primary is None:
                print(f"[sysatlas] view {view_name!r} has no architecture model; skipping render")
                continue

            self._inject_stubs(primary, view_name, component_view)
            extras = self._collect_trace_overlays(primary, view, component_view)
            xmls[view_name] = primary._to_xml(extra_edges=extras)

        # If no views were declared, fall back to rendering every architecture model
        # as its own tab so the user still gets something usable.
        if not xmls:
            xmls = {n: sm._to_xml() for n, sm in self._architecture_models.items()}

        html = render_collection(xmls, self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))

    def _collect_trace_overlays(self, sm: SystemMap, view: View,
                                component_view: dict[str, str]) -> list[dict]:
        """For each trace link whose endpoints can be reached in this view,
        return an overlay edge spec. Endpoints not local but defined in
        another view are added as stubs so the overlay has somewhere to land.

        Crucially, overlays are NOT added to the SystemMap's connections list,
        so they don't influence Sugiyama. They are appended at render time as
        post-layout dashed edges between known cells.
        """
        local_components = set(sm.diagram.components.keys())
        overlays: list[dict] = []
        for link in self._traces:
            for end in (link.source, link.target):
                if end.entity in local_components:
                    continue
                origin = component_view.get(end.entity)
                if origin and origin != view.name:
                    sm.add_component(end.entity, is_stub=True, defined_in=origin)
                    local_components.add(end.entity)
            if (link.source.entity in local_components
                    and link.target.entity in local_components):
                overlays.append({
                    "source": link.source.entity,
                    "target": link.target.entity,
                    "label":  link.kind,
                })
        return overlays

    @staticmethod
    def _inject_stubs(sm: SystemMap, view_name: str,
                      component_view: dict[str, str]) -> None:
        """Scan the SystemMap's connections; for any endpoint that is not a
        local component but IS defined in another view, insert a stub
        component locally so the connection has something to attach to."""
        local = set(sm.diagram.components.keys())
        for conn in sm.diagram.connections:
            for endpoint in (conn.source, conn.target):
                if endpoint in local:
                    continue
                origin = component_view.get(endpoint)
                if origin and origin != view_name:
                    sm.add_component(endpoint, is_stub=True, defined_in=origin)
                    local.add(endpoint)

    def save_trace_matrix(self, path: str, title: str | None = None) -> None:
        """Write an HTML matrix of all trace links to `path`.

        Independent of the diagram render; suitable for audit-style review
        ("what realizes what, what depends on what, where are the gaps").
        """
        from sysatlas._trace_matrix import render_trace_matrix
        html = render_trace_matrix(self._traces, title=title or f"{self._title} — Trace Matrix")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def show(self, viewer: str = "cdn") -> None:
        """Render and open in a browser via a temp file."""
        import tempfile
        import webbrowser
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.close()
        self.save(tmp.name, viewer=viewer)
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")
