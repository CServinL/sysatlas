"""Demo: ISO 25010 quality attribute badges on nodes and edges.

Components carry `qualities=[QualityAttribute(...)]`. Connections do
too. The renderer shows a coloured letter badge for each quality whose
criticality is >= "high" (lower criticalities exist but stay hidden to
avoid badge spam).

Colour key (also defined in `_render._QUALITY_COLOR`):
  S red    = security
  P purple = performance_efficiency
  R blue   = reliability
  M lime   = maintainability
  ...etc.

Run: python docs/demos/qualities.py
"""
import sysatlas
from sysatlas._ontology.qualities import QualityAttribute

m = sysatlas.SystemMap(title="Quality attributes")

m.group("services", color="#dcfce7")
m.group("data",     color="#fed7aa")

m.add_component(
    "API", group="services", layer="services", tech="Envoy",
    qualities=[
        QualityAttribute(category="performance_efficiency",
                         subcategory="time_behaviour",
                         criticality="high", note="p99 < 200ms"),
        QualityAttribute(category="security",
                         subcategory="authenticity",
                         criticality="critical"),
    ],
)
m.add_component(
    "Auth", group="services", layer="services", tech="Go",
    qualities=[
        QualityAttribute(category="security",
                         subcategory="confidentiality",
                         criticality="critical"),
    ],
)
m.add_component(
    "Cache", group="data", layer="data", tech="Redis",
    qualities=[
        QualityAttribute(category="performance_efficiency", criticality="critical"),
        QualityAttribute(category="reliability",
                         subcategory="availability",
                         criticality="high", note="99.9% monthly"),
        QualityAttribute(category="maintainability", criticality="high"),
    ],
)

# qualities on a connection too
m.connect("API", "Auth", label="verify",
          qualities=[
              QualityAttribute(category="security", criticality="critical"),
              QualityAttribute(category="performance_efficiency",
                               criticality="high",
                               note="add <= 20ms"),
          ])
m.connect("API", "Cache", label="lookup",
          qualities=[
              QualityAttribute(category="performance_efficiency",
                               criticality="critical"),
              QualityAttribute(category="reliability",
                               subcategory="availability",
                               criticality="high"),
          ])

m.show()
