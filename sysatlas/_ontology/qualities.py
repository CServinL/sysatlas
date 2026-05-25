"""Quality attributes per ISO/IEC 25010:2011 (Product Quality Model).

Lets components and connections be tagged with quality characteristics
("Cache is performance-critical", "Auth Service is security-sensitive",
"Storefront API has high availability requirements") in a typed,
standards-aligned way.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


QualityCategory = Literal[
    "functional_suitability",
    "performance_efficiency",
    "compatibility",
    "usability",
    "reliability",
    "security",
    "maintainability",
    "portability",
]
"""The eight top-level ISO 25010 quality characteristics."""


# Allowed subcategories per ISO 25010. Open-ended — users may pass other
# strings; validation only checks the top category.
SUBCATEGORIES: dict[QualityCategory, tuple[str, ...]] = {
    "functional_suitability": ("completeness", "correctness", "appropriateness"),
    "performance_efficiency": ("time_behaviour", "resource_utilization", "capacity"),
    "compatibility":          ("coexistence", "interoperability"),
    "usability":              ("appropriateness_recognizability", "learnability",
                                "operability", "user_error_protection",
                                "ui_aesthetics", "accessibility"),
    "reliability":            ("maturity", "availability", "fault_tolerance",
                                "recoverability"),
    "security":               ("confidentiality", "integrity", "non_repudiation",
                                "accountability", "authenticity"),
    "maintainability":        ("modularity", "reusability", "analysability",
                                "modifiability", "testability"),
    "portability":            ("adaptability", "installability", "replaceability"),
}


Criticality = Literal["low", "medium", "high", "critical"]


class QualityAttribute(BaseModel):
    """A single quality requirement / characteristic asserted about
    something (component, connection, view…)."""
    model_config = ConfigDict(extra="forbid")
    category: QualityCategory
    subcategory: str | None = None
    """Free-text but typically one of `SUBCATEGORIES[category]`."""
    criticality: Criticality = "medium"
    note: str | None = None
    """Human-readable detail: target value, rationale, measurement method."""

    def __str__(self) -> str:
        sub = f".{self.subcategory}" if self.subcategory else ""
        return f"{self.category}{sub}[{self.criticality}]"
