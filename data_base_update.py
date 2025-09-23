from __init__ import db
from bson.objectid import ObjectId

all_sales = list(db.Sales.find())

for sale in all_sales:
    if "sale_items" not in sale:
        sale["sale_items"] = [{
            "item_id": sale.get("item_id"),
            "quantity": sale.get("quantity"),
            "unit_price": sale.get("unit_price")
        }]
        db.Sales.update_one({"_id": ObjectId(sale["_id"])}, {"$set": {"sale_items": sale["sale_items"]}})
        db.Sales.update_one({"_id": ObjectId(sale["_id"])}, {"$unset": {"item_id": "", "quantity": "", "unit_price": ""}})