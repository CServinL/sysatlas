"""
Demo: full e-commerce platform architecture.
Run: python docs/demos/architecture.py
"""
import sysatlas

m = sysatlas.SystemMap(strategy="layered", title="E-Commerce Platform")

m.group("edge",      color="#dbeafe", label="Edge")
m.group("services",  color="#dcfce7", label="Services")
m.group("async",     color="#fef9c3", label="Async")
m.group("data",      color="#fed7aa", label="Data")
m.group("infra",     color="#f3e8ff", label="Infra")

# Edge
m.add_component("CDN",           group="edge",     layer="edge",     tech="CloudFront")
m.add_component("API Gateway",   group="edge",     layer="edge",     tech="Envoy")
m.add_component("Auth Service",  group="edge",     layer="edge",     tech="Go")

# Services
m.add_component("Catalog",       group="services", layer="services", tech="Python")
m.add_component("Cart",          group="services", layer="services", tech="Go")
m.add_component("Orders",        group="services", layer="services", tech="Java")
m.add_component("Payments",      group="services", layer="services", tech="Go")
m.add_component("Notifications", group="services", layer="services", tech="Python")

# Async
m.add_component("Event Bus",     group="async",    layer="async",    tech="Kafka")
m.add_component("Worker",        group="async",    layer="async",    tech="Python")

# Data
m.add_component("Catalog DB",    group="data",     layer="data",     tech="PostgreSQL")
m.add_component("Orders DB",     group="data",     layer="data",     tech="PostgreSQL")
m.add_component("Cache",         group="data",     layer="data",     tech="Redis")
m.add_component("Object Store",  group="data",     layer="data",     tech="S3")

# Infra
m.add_component("Metrics",       group="infra",    layer="infra",    tech="Prometheus")
m.add_component("Tracing",       group="infra",    layer="infra",    tech="Jaeger")

# Edge routing
m.connect("CDN",          "API Gateway",   label="HTTPS")
m.connect("API Gateway",  "Auth Service",  label="verify")
m.connect("API Gateway",  "Catalog",       label="REST")
m.connect("API Gateway",  "Cart",          label="REST")
m.connect("API Gateway",  "Orders",        label="REST")

# Service interactions
m.connect("Cart",         "Catalog",       label="prices")
m.connect("Orders",       "Payments",      label="gRPC")
m.connect("Orders",       "Event Bus",     label="publish")
m.connect("Payments",     "Event Bus",     label="publish")

# Async processing
m.connect("Event Bus",    "Worker",        label="consume")
m.connect("Worker",       "Notifications", label="trigger")

# Data
m.connect("Catalog",      "Catalog DB",    label="SQL")
m.connect("Catalog",      "Cache",         label="read")
m.connect("Cart",         "Cache",         label="session")
m.connect("Orders",       "Orders DB",     label="SQL")
m.connect("Notifications","Object Store",  label="templates")

# Observability
m.connect("API Gateway",  "Tracing",       label="spans")
m.connect("Orders",       "Metrics",       label="metrics")
m.connect("Payments",     "Metrics",       label="metrics")

m.show(debug=True)
