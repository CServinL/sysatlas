# Sequence Diagram — Ontology

A UML sequence diagram shows **interactions over time** between participants:
who calls whom, in what order, and for how long each participant is active.
Layout is dominated by a vertical time axis with one lifeline per actor.

## Concepts

| Concept | Purpose |
|---|---|
| `Actor` | A participant: user, system, boundary, control, entity. Has a vertical lifeline. |
| `Message` | A directed call between actors at a specific point in time. |
| `Activation` | Period where an actor is actively executing (rectangle on lifeline). |
| `Frame` | Combined fragment wrapping a range of messages (`alt`, `opt`, `loop`, `par`, `critical`). |

## Message kinds

- `sync` — synchronous call (solid arrow, filled head).
- `async` — asynchronous (solid arrow, open head).
- `reply` — return (dashed arrow).
- `create` — instance creation.
- `destroy` — instance destruction.

## Schema

Source: `sysatlas/_ontology/sequence.py`

```python
class Actor(BaseModel):
    name: str
    kind: Literal["actor", "system", "boundary", "control", "entity"] = "system"

class Message(BaseModel):
    source: str                     # → Actor.name
    target: str                     # → Actor.name
    label: str = ""
    kind: MessageKind = "sync"
    order: int = 0                  # 0-based sequence index

class Activation(BaseModel):
    actor: str
    start_order: int                # message index where it starts
    end_order: int

class Frame(BaseModel):
    kind: FrameKind                 # "alt"/"opt"/"loop"/"par"/"critical"
    label: str = ""                 # condition / guard
    start_order: int
    end_order: int
```

## Validation

- `Message.source` and `.target` must reference known `Actor`s.
- `Activation.actor` must be a known `Actor`.
- Activation/frame `start_order <= end_order`.

## Notes

Time order is the **only** spatial dimension that matters; messages are
plotted at `y = order * spacing`. Actors are at fixed `x`. Frames are
rendered as rectangles spanning the range of messages they wrap.
