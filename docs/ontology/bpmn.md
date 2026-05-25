# BPMN Process Diagram — Ontology

BPMN models a **business process** as a left-to-right flow of events,
activities, and gateways, organized into pools (participants) and lanes
(roles). This ontology covers a *simplified* subset suitable for
documentation; full BPMN 2.0 has many more constructs.

## Concepts

| Concept | Purpose |
|---|---|
| `Pool` | A participant: organization, system, role. Top-level container. |
| `Lane` | A horizontal swimlane inside a pool: a department, team, role. |
| `Event` | Something that happens: start, end, intermediate, timer, message, error. |
| `Activity` | A unit of work: task, user task, service task, subprocess. |
| `Gateway` | Branching/merging point: exclusive (XOR), parallel (AND), inclusive (OR), event-based. |
| `Flow` | A directed connection between flow nodes (events/activities/gateways). |

## Event kinds

| Kind | When | Notation |
|---|---|---|
| `start` | process begins | thin-border circle |
| `end` | process ends | thick-border circle |
| `intermediate` | happens mid-process | double-border circle |
| `timer` | time-based trigger | clock icon inside circle |
| `message` | message arrival | envelope icon |
| `error` | error caught/thrown | lightning icon |

## Activity kinds

`task`, `user_task` (human), `service_task` (automated), `subprocess`,
`call_activity` (invokes another process).

## Gateway kinds

| Kind | Symbol | Behavior |
|---|---|---|
| `exclusive` (XOR) | empty diamond / `X` | exactly one outgoing path |
| `parallel` (AND) | `+` diamond | all outgoing paths concurrently |
| `inclusive` (OR) | `O` diamond | any subset of outgoing paths |
| `event_based` | pentagon-in-diamond | wait for the first of several events |

## Flow kinds

- `sequence` — normal process flow (solid arrow).
- `message` — between pools, asynchronous (dashed arrow).
- `default` — fallback when guards fail (slashed arrow).
- `conditional` — guarded sequence flow (diamond on tail).

## Schema

Source: `sysatlas/_ontology/bpmn.py`

```python
class Pool(BaseModel):    name: str
class Lane(BaseModel):    name: str; pool: str
class Event(BaseModel):   name: str; kind: EventKind = "intermediate"; lane: str | None = None
class Activity(BaseModel):name: str; kind: ActivityKind = "task";       lane: str | None = None
class Gateway(BaseModel): name: str; kind: GatewayKind = "exclusive";   lane: str | None = None
class Flow(BaseModel):    source: str; target: str; kind: FlowKind = "sequence"
```

## Validation

- Lane must reference an existing Pool.
- Each Event/Activity/Gateway's `lane` must exist if specified.
- Names must be unique across all flow-node types (events + activities + gateways).
- Flow endpoints must be known flow nodes.
