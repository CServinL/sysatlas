# Quality Attributes (ISO 25010)

Components and connections can be tagged with **quality attributes**
from the ISO/IEC 25010:2011 Product Quality Model. This lets a diagram
carry semantics like "Cache is performance-critical", "Auth Service is
security-sensitive", "the link from API to Payments has high
availability requirements".

## The eight ISO 25010 categories

| Category | What it covers (typical subcategories) |
|---|---|
| `functional_suitability` | completeness, correctness, appropriateness |
| `performance_efficiency` | time_behaviour, resource_utilization, capacity |
| `compatibility` | coexistence, interoperability |
| `usability` | learnability, operability, error protection, aesthetics, accessibility |
| `reliability` | maturity, availability, fault_tolerance, recoverability |
| `security` | confidentiality, integrity, non_repudiation, accountability, authenticity |
| `maintainability` | modularity, reusability, analysability, modifiability, testability |
| `portability` | adaptability, installability, replaceability |

Use the top-level category as the primary tag. The subcategory is
optional and free-text (typical values are predefined in
`SUBCATEGORIES` for convenience).

## Schema

Source: `sysatlas/_ontology/qualities.py`

```python
QualityCategory = Literal[
    "functional_suitability", "performance_efficiency", "compatibility",
    "usability", "reliability", "security", "maintainability", "portability",
]

Criticality = Literal["low", "medium", "high", "critical"]

class QualityAttribute(BaseModel):
    category: QualityCategory
    subcategory: str | None = None        # typically one of SUBCATEGORIES[category]
    criticality: Criticality = "medium"
    note: str | None = None               # target value, rationale, measurement
```

## Where they live

Currently attached to:

- `architecture.Component.qualities`
- `architecture.Connection.qualities`

Other Model Kinds (Class, Activity, Process, …) can adopt the same
field when needed; the type is intentionally cross-cutting.

## Example

```python
from sysatlas._ontology.qualities import QualityAttribute
from sysatlas._ontology.architecture import Component, Connection

cache = Component(
    name="Cache",
    tech="Redis",
    qualities=[
        QualityAttribute(
            category="performance_efficiency",
            subcategory="time_behaviour",
            criticality="critical",
            note="p99 lookup < 5ms",
        ),
        QualityAttribute(
            category="reliability",
            subcategory="availability",
            criticality="high",
            note="99.9% monthly",
        ),
    ],
)

auth_link = Connection(
    source="ApiGateway",
    target="AuthService",
    label="verify",
    qualities=[
        QualityAttribute(
            category="security",
            subcategory="confidentiality",
            criticality="critical",
        ),
        QualityAttribute(
            category="performance_efficiency",
            subcategory="time_behaviour",
            criticality="high",
            note="add ≤ 20ms to request",
        ),
    ],
)
```

## Visualisation (future)

Qualities are currently model-only — they validate and serialize but
don't influence rendering. Planned options:

- Coloured badges on nodes / edges keyed by category.
- Filter views by quality (e.g. "show only security-critical paths").
- Per-quality view-kind (an *availability map* highlighting all
  components/links with availability requirements).
