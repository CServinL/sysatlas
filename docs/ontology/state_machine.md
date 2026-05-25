# State Machine Diagram — Ontology

A state chart models **discrete states** of a single entity and the
**transitions** between them triggered by events.

## Concepts

| Concept | Purpose |
|---|---|
| `State` | A discrete situation the entity can be in. |
| `Transition` | A directed edge between two states, optionally fired by an event, guarded by a condition, with a side-effect action. |

## State kinds

| Kind | Notation | Purpose |
|---|---|---|
| `normal` | rounded rectangle | regular state |
| `initial` | filled black dot | entry point (exactly one required) |
| `final` | bullseye | terminal state (no outgoing transitions) |
| `choice` | diamond | conditional branching point |
| `composite` | rounded rectangle with nested states | contains child states (use `parent`) |

## Transition labels

A transition label has the form `event [guard] / action`:

- `event` — what triggered it.
- `guard` — boolean condition (taken only if true).
- `action` — side-effect executed on transition.

Any of the three can be omitted.

## Schema

Source: `sysatlas/_ontology/state_machine.py`

```python
class State(BaseModel):
    name: str
    kind: StateKind = "normal"
    parent: str | None = None       # for nesting in composite states
    entry_action: str | None = None
    exit_action: str | None = None
    do_activity: str | None = None

class Transition(BaseModel):
    source: str
    target: str
    event: str = ""
    guard: str = ""
    action: str = ""
```

## Validation

- At least one state with `kind="initial"`.
- All `Transition.source`/`.target` reference known states.
- A `final` state cannot have outgoing transitions.
- `State.parent` (for nesting) must reference a known state.
