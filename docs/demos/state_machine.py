"""Demo: state machine via StateMap.

Order lifecycle. Filled circle = initial pseudo-state; bullseye =
final pseudo-state. Transition labels carry event [guard] / action.

Run: python docs/demos/state_machine.py
"""
import sysatlas

s = sysatlas.StateMap(title="Order lifecycle")

s.initial("start")
s.state("Pending", entry="reserve_stock")
s.state("Paid",    do="charge_card")
s.state("Shipped", entry="notify_carrier")
s.state("Delivered")
s.state("Cancelled")
s.final("end")

s.transition("start",     "Pending")
s.transition("Pending",   "Paid",      event="payment_received")
s.transition("Pending",   "Cancelled", event="timeout", guard="age>72h")
s.transition("Paid",      "Shipped",   event="picked_up")
s.transition("Paid",      "Cancelled", event="refund_requested")
s.transition("Shipped",   "Delivered", event="signature_collected")
s.transition("Delivered", "end")
s.transition("Cancelled", "end")

s.show()
