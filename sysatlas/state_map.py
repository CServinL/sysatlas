"""Fluent builder for state machine diagrams."""
from __future__ import annotations

from typing import Literal

from sysatlas._ontology.state_machine import State, StateDiagram, Transition
from sysatlas._render import copy_local_viewer
from sysatlas._state_render import render_state

StateKind = Literal["normal", "initial", "final", "choice", "composite"]


class StateMap:
    """Build a state machine one state and transition at a time."""

    def __init__(self, title: str = "") -> None:
        self._states: dict[str, State] = {}
        self._transitions: list[Transition] = []
        self._title = title

    @property
    def diagram(self) -> StateDiagram:
        return StateDiagram(title=self._title, states=self._states,
                            transitions=self._transitions)

    def state(self, name: str, *, kind: StateKind = "normal",
              label: str | None = None, parent: str | None = None,
              entry: str | None = None, exit: str | None = None,
              do: str | None = None) -> "StateMap":
        self._states[name] = State(
            name=name, kind=kind, label=label, parent=parent,
            entry_action=entry, exit_action=exit, do_activity=do,
        )
        return self

    def initial(self, name: str = "__initial__", *, parent: str | None = None) -> "StateMap":
        return self.state(name, kind="initial", parent=parent)

    def final(self, name: str = "__final__", *, parent: str | None = None) -> "StateMap":
        return self.state(name, kind="final", parent=parent)

    def transition(self, source: str, target: str, *, event: str = "",
                   guard: str = "", action: str = "") -> "StateMap":
        self._transitions.append(Transition(
            source=source, target=target,
            event=event, guard=guard, action=action,
        ))
        return self

    def show(self, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        html = render_state(self.diagram, title=self._title, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        html = render_state(self.diagram, title=self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
