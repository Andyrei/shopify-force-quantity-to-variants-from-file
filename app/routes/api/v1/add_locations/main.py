from collections import defaultdict
from unittest import result
from app.utilities.shopify import adjust_quantity_to_variant, get_product_variants_by_sku, set_activate_quantity_on_location



def __group_variants_by_product_id(product_variants, data_rows):
    """
    
    Example usage:
        grouped = group_variants_by_product_id(product_variants)
        for product_id, variants in grouped.items():
            print(product_id, variants)
        
    """
    grouped = defaultdict(list)
    for variant in product_variants:
        for row in data_rows:
            if variant["sku"] == row["sku"]:
                variant["quantity"] = row["qta"]
                variant["location"] = row["id sede"]
    return dict(grouped)


def get_product_variants_and_sync(data_rows) -> list[dict, list]:
    
    # print(data_rows)
    prod_reference = []
    for row in data_rows:
        prod_reference.append(row["sku"])

    product_variants = get_product_variants_by_sku(prod_reference)

    # Find missing SKUs
    found_skus = {variant["sku"] for variant in product_variants}
    missing_skus = [sku for sku in prod_reference if sku not in found_skus]
    
    inventories = []
    for variant in product_variants:
        for row in data_rows:
            if variant["sku"] == row["sku"]:
                inventory_item = variant["inventoryItem"]["id"]
                location_id = f"gid://shopify/Location/{row["id sede"]}"
                
                set_activate_quantity_on_location(inventoryItemId=inventory_item, locationId=location_id)
                
                inventories.append({
                    "delta": 2, # quantità
                    "inventoryItemId": inventory_item,
                    "locationId": location_id
                })
    result = adjust_quantity_to_variant(inventories=inventories)
    
    print(result)
    return result, missing_skus