# Entity-Relationship Diagram — Ontology

An ER diagram models a **relational data schema** at conceptual or logical
level: entities (things), their attributes (data fields), and the
relationships (associations) between them with explicit **cardinality**.

## Concepts

| Concept | Purpose |
|---|---|
| `Entity` | A thing whose data is stored (User, Order, Product). Optionally a *weak entity* if it depends on another for identity. |
| `Attribute` | A field on an entity. May be a primary key (`is_key`) and/or required (`is_required`). |
| `Relationship` | A directed association between two entities with cardinalities on both sides. |

## Cardinalities

Standard Chen / crow's-foot notation:

| Code | Meaning |
|---|---|
| `1` | exactly one |
| `0..1` | zero or one |
| `*` | many (zero or more) |
| `1..*` | one or more |

## Schema

Source: `sysatlas/_ontology/er.py`

```python
class Attribute(BaseModel):
    name: str
    type: str | None = None        # e.g. "varchar(64)"
    is_key: bool = False
    is_required: bool = False

class Entity(BaseModel):
    name: str
    label: str | None = None
    attributes: list[Attribute]
    is_weak: bool = False

class Relationship(BaseModel):
    name: str                       # "places", "contains"
    source: str                     # → Entity.name
    target: str                     # → Entity.name
    source_card: Cardinality = "1"
    target_card: Cardinality = "*"
    is_identifying: bool = False    # for weak entities
```

## Validation

- Every `Relationship.source` and `.target` must reference a known `Entity`.

## Builder

`sysatlas.ERMap` is the fluent builder. See
[`../demos/er.py`](../demos/er.py).

```python
import sysatlas

e = sysatlas.ERMap(title="Shop")
e.entity("Customer")
e.attribute("Customer", "id",    type="uuid", is_key=True)
e.attribute("Customer", "email", is_required=True)
e.entity("Order")
e.attribute("Order", "id", type="uuid", is_key=True)
e.relate("Customer", "Order", name="places", source_card="1", target_card="*")
e.save("shop.html")
```

Methods: `entity`, `attribute`, `relate`, `show`, `save`. `attribute()`
auto-creates the entity if it doesn't exist yet.

## Distinction from Class diagrams

ER focuses on **data shape**: what's stored, how rows relate. Class
diagrams (`uml_class.md`) focus on **code shape**: methods, inheritance,
visibility. Use ER for database design and data modelling.
