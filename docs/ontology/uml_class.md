# Class Diagram (UML) — Ontology

UML class diagrams describe **static structure** of an object-oriented
system: classes, their attributes and methods, and their structural and
behavioral relationships.

## Concepts

| Concept | Purpose |
|---|---|
| `Class` | A class, abstract class, interface, or enum. Has attributes and methods. |
| `Attribute` | A data member with type and visibility. |
| `Method` | A function member with return type, params, visibility, abstractness. |
| `Relation` | Directed relationship between two classes. |

## Relation kinds

| Kind | Meaning | UML notation |
|---|---|---|
| `inheritance` | "is-a" | hollow triangle to parent |
| `implementation` | implements interface | dashed line + hollow triangle |
| `composition` | "owns" (strong, dependent lifetime) | filled diamond at owner |
| `aggregation` | "has" (weak, shared lifetime) | hollow diamond at owner |
| `association` | "uses" | plain line |
| `dependency` | "depends on" | dashed arrow |

## Visibility

`public` (+), `private` (-), `protected` (#), `package` (~).

## Schema

Source: `sysatlas/_ontology/uml_class.py`

```python
class Attribute(BaseModel):
    name: str
    type: str | None = None
    visibility: Visibility = "public"
    is_static: bool = False

class Method(BaseModel):
    name: str
    return_type: str | None = None
    params: list[str]              # ["x: int", "y: str"]
    visibility: Visibility = "public"
    is_static: bool = False
    is_abstract: bool = False

class Class(BaseModel):
    name: str
    kind: ClassKind = "class"      # "class"/"abstract"/"interface"/"enum"
    attributes: list[Attribute]
    methods: list[Method]

class Relation(BaseModel):
    source: str
    target: str
    kind: RelationKind = "association"
    label: str = ""
    source_multiplicity: str = ""   # "1", "0..*"
    target_multiplicity: str = ""
```

## Validation

- All `Relation.source` and `.target` must reference known `Class`es.
- A class cannot inherit from itself.

## Builder

`sysatlas.ClassMap` is the fluent builder. See
[`../demos/uml_class.py`](../demos/uml_class.py).

```python
import sysatlas

c = sysatlas.ClassMap(title="Payments")
c.cls("Payment", kind="abstract")
c.method("Payment", "charge", return_type="bool", is_abstract=True)
c.cls("CardPayment")
c.attribute("CardPayment", "card_id", type="str")
c.relate("CardPayment", "Payment", kind="inheritance")
c.save("payments.html")
```

Methods: `cls`, `attribute`, `method`, `relate`, `show`, `save`.
Inheritance and implementation relations drive top-down ranking;
other relation kinds (composition, aggregation, association,
dependency) overlay on that hierarchy.

## Distinction from ER

UML Class is about **code structure** (methods, inheritance, visibility).
ER (`er.md`) is about **data shape** (cardinality of rows, primary keys).
