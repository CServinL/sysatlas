"""Demo: BPMN process diagram via BPMNMap.

A two-lane purchase order flow inside one pool. Start event in the
Sales lane, branches at an exclusive gateway based on approval needed,
and merges before the end event in Finance.

Run: python docs/demos/bpmn.py
"""
import sysatlas

b = sysatlas.BPMNMap(title="Purchase order")

b.pool("Company")
b.lane("sales",   pool="Company", label="Sales")
b.lane("finance", pool="Company", label="Finance")

b.event("start",   kind="start",   lane="sales")
b.activity("intake",  kind="user_task",    lane="sales", label="Take order")
b.activity("validate",kind="service_task", lane="sales", label="Validate")
b.gateway("needs_approval", kind="exclusive", lane="sales", label="approval?")

b.activity("approve", kind="user_task", lane="finance", label="Approve")
b.gateway("merge", kind="exclusive", lane="finance")
b.activity("post", kind="service_task", lane="finance", label="Post to ledger")
b.event("end", kind="end", lane="finance")

b.flow("start",          "intake")
b.flow("intake",         "validate")
b.flow("validate",       "needs_approval")
b.flow("needs_approval", "approve", label="> $10k", kind="conditional")
b.flow("needs_approval", "merge",   label="auto",   kind="default")
b.flow("approve",        "merge")
b.flow("merge",          "post")
b.flow("post",           "end")

b.show()
