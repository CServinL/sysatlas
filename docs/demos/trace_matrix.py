"""Demo: trace links rendered both as overlay edges and as an HTML matrix.

A trace link semantically connects two entities across models (e.g. a
class realizes a component, a component depends on a payment service,
a use-case satisfies a requirement). sysatlas renders them in two ways:

- **Overlay on a diagram view** — dashed purple edges added AFTER the
  Sugiyama layout, so they don't shift placement.
- **HTML trace matrix** — a sources × targets table, coloured by link
  kind, for audit-style analysis.

Run: python docs/demos/trace_matrix.py
"""
import sysatlas

s = sysatlas.System(title="E-Commerce")

s.viewpoint("container", model_kinds=["architecture"])

# Two architecture views.
sf = s.architecture_model("storefront")
sf.group("services", color="#dcfce7")
sf.add_component("Cart",    group="services", layer="services", tech="Go")
sf.add_component("Catalog", group="services", layer="services", tech="Python")
sf.add_component("Search",  group="services", layer="services", tech="Python")
sf.connect("Cart",   "Catalog", label="prices")
sf.connect("Search", "Catalog", label="query")

pm = s.architecture_model("payments")
pm.group("services", color="#dcfce7")
pm.add_component("Payments", group="services", layer="services", tech="Java")
pm.add_component("Gateway",  group="services", layer="services", tech="Go")
pm.add_component("Fraud",    group="services", layer="services", tech="Python")
pm.connect("Payments", "Gateway", label="HTTPS")
pm.connect("Payments", "Fraud",   label="risk-check")

# A separate UML class model — also registered as an architecture
# model so the System builder picks it up; treat its components as the
# classes they represent.
uml = s.architecture_model("uml-storefront")
uml.add_component("CartController")
uml.add_component("CatalogService")

s.view("storefront-view", viewpoint="container", models=["storefront"])
s.view("payments-view",   viewpoint="container", models=["payments"])

# Trace links: cross-model semantics.
s.trace("uml-storefront#CartController",  "storefront#Cart",     kind="realizes")
s.trace("uml-storefront#CatalogService",  "storefront#Catalog",  kind="realizes")
s.trace("storefront#Cart",                "payments#Payments",   kind="depends_on")
s.trace("storefront#Search",              "storefront#Catalog",  kind="depends_on")
s.trace("payments#Payments",              "payments#Gateway",    kind="depends_on")
s.trace("payments#Payments",              "payments#Fraud",      kind="depends_on",
        note="risk check before authorize")
s.trace("storefront#Cart",                "payments#Gateway",    kind="documents",
        note="see Cart.checkout()")

# 1) Multi-tab diagram with trace links as dashed overlays per view.
s.save("/tmp/sysatlas_demo_traces_diagram.html", viewer="embed")
print("Diagram with overlay traces  -> /tmp/sysatlas_demo_traces_diagram.html")

# 2) Audit-style trace matrix.
s.save_trace_matrix("/tmp/sysatlas_demo_traces_matrix.html")
print("Trace matrix (sources x targets) -> /tmp/sysatlas_demo_traces_matrix.html")
