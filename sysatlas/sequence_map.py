"""Fluent builder for UML sequence diagrams."""
from __future__ import annotations

from typing import Literal

from sysatlas._ontology.sequence import (
    Activation, Actor, Frame, Message, SequenceDiagram,
)
from sysatlas._render import copy_local_viewer
from sysatlas._sequence_render import render_sequence

ActorKind   = Literal["actor", "system", "boundary", "control", "entity"]
MessageKind = Literal["sync", "async", "reply", "create", "destroy"]
FrameKind   = Literal["alt", "opt", "loop", "par", "critical"]


class SequenceMap:
    """Build a sequence diagram one actor / message at a time."""

    def __init__(self, title: str = "") -> None:
        self._actors: dict[str, Actor] = {}
        self._messages: list[Message] = []
        self._activations: list[Activation] = []
        self._frames: list[Frame] = []
        self._title = title
        self._next_order = 1

    @property
    def diagram(self) -> SequenceDiagram:
        return SequenceDiagram(
            title=self._title,
            actors=self._actors,
            messages=self._messages,
            activations=self._activations,
            frames=self._frames,
        )

    def actor(self, name: str, *, kind: ActorKind = "system",
              label: str | None = None) -> "SequenceMap":
        self._actors[name] = Actor(name=name, kind=kind, label=label)
        return self

    def send(self, source: str, target: str, *, label: str = "",
             kind: MessageKind = "sync", order: int | None = None) -> "SequenceMap":
        for n in (source, target):
            if n not in self._actors:
                self._actors[n] = Actor(name=n)
        if order is None:
            order = self._next_order
            self._next_order += 1
        else:
            self._next_order = max(self._next_order, order + 1)
        self._messages.append(Message(
            source=source, target=target, label=label, kind=kind, order=order,
        ))
        return self

    def activate(self, actor: str, start_order: int, end_order: int) -> "SequenceMap":
        self._activations.append(Activation(
            actor=actor, start_order=start_order, end_order=end_order,
        ))
        return self

    def frame(self, kind: FrameKind, start_order: int, end_order: int,
              label: str = "") -> "SequenceMap":
        self._frames.append(Frame(
            kind=kind, start_order=start_order, end_order=end_order, label=label,
        ))
        return self

    def show(self, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        html = render_sequence(self.diagram, title=self._title, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        html = render_sequence(self.diagram, title=self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
