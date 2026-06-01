"""Demo: Entity-Relationship diagram via ERMap.

E-commerce mini schema. Entities own attributes (keys + required); each
relationship has a name and cardinalities on both sides.

Run: python docs/demos/er.py
"""
import sysatlas

e = sysatlas.ERMap(title="Shop")

e.entity("Customer")
e.attribute("Customer", "id",    type="uuid",      is_key=True)
e.attribute("Customer", "email", type="varchar",   is_required=True)
e.attribute("Customer", "name",  type="varchar")

e.entity("Order")
e.attribute("Order", "id",         type="uuid",   is_key=True)
e.attribute("Order", "placed_at",  type="ts",     is_required=True)
e.attribute("Order", "total",      type="money",  is_required=True)

e.entity("LineItem", is_weak=True)
e.attribute("LineItem", "line_no", type="int", is_key=True)
e.attribute("LineItem", "qty",     type="int", is_required=True)
e.attribute("LineItem", "price",   type="money")

e.entity("Product")
e.attribute("Product", "sku",   type="varchar", is_key=True)
e.attribute("Product", "name",  type="varchar", is_required=True)
e.attribute("Product", "price", type="money")

e.relate("Customer", "Order",    name="places",   source_card="1", target_card="*")
e.relate("Order",    "LineItem", name="contains", source_card="1", target_card="1..*",
         is_identifying=True)
e.relate("Product",  "LineItem", name="sold_as",  source_card="1", target_card="*")

e.show()
