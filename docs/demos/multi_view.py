"""Demo: multi-view Architecture Description via System.

The same e-commerce system split into focused views. A connection from
one view's component to another's auto-becomes a stub on render
(dashed/faded box) — preserving cross-view identity without forcing one
giant diagram.

Run: python docs/demos/multi_view.py
"""
import sysatlas

s = sysatlas.System(title="E-Commerce")

s.stakeholder("dev", role="Developer")
s.stakeholder("ops", role="Platform Ops")
s.concern("latency",      stakeholders=["dev", "ops"])
s.concern("deployability", stakeholders=["ops"])
s.viewpoint(
    "container",
    concerns=["latency", "deployability"],
    model_kinds=["architecture"],
    conventions="C4 container view with layered grouping",
)

# ── Storefront ──────────────────────────────────────────────────────
sf = s.architecture_model("storefront")
sf.group("edge",     color="#dbeafe")
sf.group("services", color="#dcfce7")
sf.add_component("API Gateway", group="edge",     layer="edge",     tech="Envoy")
sf.add_component("Catalog",     group="services", layer="services", tech="Python")
sf.add_component("Cart",        group="services", layer="services", tech="Go")
sf.connect("API Gateway", "Catalog", label="REST")
sf.connect("API Gateway", "Cart",    label="REST")
sf.connect("Cart", "Catalog", label="prices")
# Cross-view: Cart talks to Payments, which is defined in another view.
sf.connect("Cart", "Payments", label="checkout")

# ── Payments ────────────────────────────────────────────────────────
pm = s.architecture_model("payments")
pm.group("services", color="#dcfce7")
pm.group("ext",      color="#fee2e2")
pm.add_component("Payments",    group="services", layer="services", tech="Java")
pm.add_component("Gateway",     group="services", layer="services", tech="Go")
pm.add_component("Fraud",       group="services", layer="services", tech="Python")
pm.add_component("Card Network",group="ext",      layer="ext",      tech="external")
pm.connect("Payments", "Gateway", label="HTTPS")
pm.connect("Payments", "Fraud",   label="risk-check")
pm.connect("Gateway",  "Card Network", label="ISO 8583")

s.view("storefront", viewpoint="container", models=["storefront"])
s.view("payments",   viewpoint="container", models=["payments"])

s.show()
