"""Hub-and-spoke strategy demo: an ontology-driven product analytics platform.

Five reserved layers position components:
  - interfaces  → top band (humans / agents)
  - write       → left column (sources writing into the hub)
  - hub         → centre (the integrating model)
  - read        → right column (consumers reading from the hub)
  - external    → bottom band (storage / artefacts)

`strategy="hub"` selects sysatlas/_hub_layout.py. Routing is
intentionally simple (straight lines) — the hub strategy assumes
bounded-complexity per view, so heavy routing is overkill.

Run: python docs/demos/hub.py
"""
import sysatlas

m = sysatlas.SystemMap(strategy="hub",
                       title="Product analytics — ontology hub")

m.add_component("Analyst",      layer="interfaces", tech="Looker / SQL")
m.add_component("AI Assistant", layer="interfaces", tech="LLM agent")

m.add_component("Web events",       layer="write", tech="Segment")
m.add_component("Billing events",   layer="write", tech="Stripe webhook")
m.add_component("Support tickets",  layer="write", tech="Zendesk API")

m.add_component("Customer 360", layer="hub", tech="Pydantic ontology")

m.add_component("Dashboards",      layer="read", tech="Looker")
m.add_component("Cohort exports",  layer="read", tech="Notebook · CSV")

m.add_component("Data warehouse", layer="external", tech="Snowflake")
m.add_component("Email campaigns", layer="external", tech="Marketing automation")

m.connect("Analyst",      "Dashboards", label="queries")
m.connect("AI Assistant", "Customer 360", label="reads schema")

m.connect("Web events",      "Customer 360", label="appends")
m.connect("Billing events",  "Customer 360", label="upserts")
m.connect("Support tickets", "Customer 360", label="appends")

m.connect("Customer 360", "Dashboards",     label="exposes")
m.connect("Customer 360", "Cohort exports", label="materialises")

m.connect("Cohort exports", "Email campaigns", label="targets")
m.connect("Dashboards",     "Data warehouse",  label="persists")

m.show()
