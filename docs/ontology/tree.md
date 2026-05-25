# Tree Diagram — Ontology

A tree diagram is a **connected acyclic graph with a single root** where
every non-root node has exactly one parent. The same primitive serves
several use cases distinguished by a `flavor` tag.

## Flavors

| Flavor | Use case | Typical labels |
|---|---|---|
| `org` | Reporting / org chart | Person or Role names |
| `mindmap` | Topic exploration around a central idea | Topics and subtopics |
| `taxonomy` | Categorical hierarchy | Biological / library / domain categories |
| `filesystem` | File and directory tree | Paths |
| `generic` | Anything tree-shaped without specific semantics | — |

These are semantic markers; the structural model is identical. Layout
hints can vary (radial for mindmap, top-down for org, etc.).

## Concepts

| Concept | Purpose |
|---|---|
| `TreeNode` | A node in the tree. References its parent by name. |

## Schema

Source: `sysatlas/_ontology/tree.py`

```python
class TreeNode(BaseModel):
    name: str                       # unique id
    label: str | None = None
    parent: str | None = None       # None for root
    kind: NodeKind = "branch"       # "root" | "branch" | "leaf"
    icon: str | None = None
    color: str | None = None

class TreeDiagram(BaseModel):
    title: str = ""
    flavor: Literal["org", "mindmap", "taxonomy", "filesystem", "generic"] = "generic"
    nodes: dict[str, TreeNode]
```

## Validation

Construction enforces tree shape:

- Exactly **one root** (node with `parent=None`).
- Every non-root `parent` must reference a known node.
- No self-parenting.
- No cycles (verified by reachability walk from the root).
- No disconnected nodes (every node must be reachable from the root).

## Distinction from other diagrams

A tree is the simplest possible diagram. Use it instead of architecture
or class diagrams when the relation is purely hierarchical (each child
has one parent) and there are no cross-references. If nodes have
multiple parents or cross-edges, use an architecture or class diagram.
