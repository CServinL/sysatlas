"""Demo: UML sequence diagram via SequenceMap.

Actors get vertical lifelines; messages flow top-to-bottom in the order
they are added. The `opt` frame wraps the optional fraud-check branch.

Run: python docs/demos/sequence.py
"""
import sysatlas

s = sysatlas.SequenceMap(title="Checkout")

s.actor("User",    kind="actor")
s.actor("Web",     kind="boundary")
s.actor("Orders",  kind="system")
s.actor("Fraud",   kind="system")
s.actor("DB",      kind="entity")

s.send("User", "Web",    label="POST /checkout")          # 1
s.send("Web",  "Orders", label="placeOrder()")            # 2
s.send("Orders", "Fraud", label="score(user, cart)")      # 3
s.send("Fraud",  "Orders", label="risk=low", kind="reply")  # 4
s.send("Orders", "DB",   label="INSERT order")            # 5
s.send("DB",     "Orders", label="ok", kind="reply")      # 6
s.send("Orders", "Web",  label="201 Created", kind="reply")  # 7
s.send("Web",    "User", label="render receipt", kind="reply")  # 8

s.activate("Web",    1, 8)
s.activate("Orders", 2, 7)
s.activate("Fraud",  3, 4)
s.activate("DB",     5, 6)

s.frame("opt", 3, 4, label="risk threshold check")

s.show()
