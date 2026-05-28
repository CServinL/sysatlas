"""Demo: UML class diagram via ClassMap.

A small payments domain showing every relation kind:
- inheritance (Payment <- CardPayment, BankPayment)
- implementation (CardPayment ..|> Auditable)
- composition (Order *-- LineItem)
- aggregation (Cart o-- Product)
- association (Customer -- Order)
- dependency (CardPayment ..> FraudClient)

Run: python docs/demos/uml_class.py
"""
import sysatlas

c = sysatlas.ClassMap(title="Payments domain")

c.cls("Auditable", kind="interface")
c.method("Auditable", "auditLog", return_type="str", is_abstract=True)

c.cls("Payment", kind="abstract")
c.attribute("Payment", "id",     type="UUID")
c.attribute("Payment", "amount", type="Money")
c.method("Payment", "charge", return_type="bool", is_abstract=True)
c.method("Payment", "refund", return_type="bool")

c.cls("CardPayment")
c.attribute("CardPayment", "card_id", type="str")
c.method("CardPayment", "charge", return_type="bool")
c.method("CardPayment", "authorize", params=["amount: Money"], return_type="str")

c.cls("BankPayment")
c.attribute("BankPayment", "iban", type="str")
c.method("BankPayment", "charge", return_type="bool")

c.cls("Customer")
c.attribute("Customer", "id",    type="UUID")
c.attribute("Customer", "email", type="str")

c.cls("Order")
c.attribute("Order", "id",    type="UUID")
c.attribute("Order", "total", type="Money")

c.cls("LineItem")
c.attribute("LineItem", "sku", type="str")
c.attribute("LineItem", "qty", type="int")

c.cls("Cart")
c.cls("Product")
c.cls("FraudClient")

c.relate("CardPayment", "Payment",    kind="inheritance")
c.relate("BankPayment", "Payment",    kind="inheritance")
c.relate("CardPayment", "Auditable",  kind="implementation")
c.relate("Order",       "LineItem",   kind="composition",
         target_multiplicity="1..*")
c.relate("Cart",        "Product",    kind="aggregation",
         target_multiplicity="*")
c.relate("Customer",    "Order",      kind="association",
         source_multiplicity="1", target_multiplicity="*")
c.relate("CardPayment", "FraudClient", kind="dependency")

c.show()
