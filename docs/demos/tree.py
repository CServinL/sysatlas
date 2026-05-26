"""Demo: top-down tree diagram via TreeMap.

Org-chart flavour. Reingold-Tilford layout: each subtree gets the
horizontal width its leaves need; parents centre over children.

Run: python docs/demos/tree.py
"""
import sysatlas

t = sysatlas.TreeMap(title="Org Chart", flavor="org")

t.add("CEO", kind="root")
t.add("CTO", parent="CEO")
t.add("CFO", parent="CEO")
t.add("COO", parent="CEO")

t.add("VP Eng",   parent="CTO")
t.add("VP Data",  parent="CTO")
t.add("VP Infra", parent="CTO")

t.add("Controller", parent="CFO")
t.add("Treasury",   parent="CFO")

t.add("Ops Director", parent="COO")

t.add("EM Frontend", parent="VP Eng")
t.add("EM Backend",  parent="VP Eng")
t.add("EM Mobile",   parent="VP Eng")

t.show()
