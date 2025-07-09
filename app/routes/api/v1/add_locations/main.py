from collections import defaultdict
from unittest import result
from app.utilities.shopify import add_to_sale_channels, adjust_quantity_to_variant, get_product_variants_by_sku, set_activate_quantity_on_location


def get_product_variants_and_sync(data_rows) -> list[dict, list]:
    
    # print(data_rows)
    prod_reference = []
    for row in data_rows:
        prod_reference.append(row["sku"])

    product_variants = get_product_variants_by_sku(prod_reference)
    
    if not product_variants:
        return [], prod_reference
    # Find missing SKUs
    found_skus = {variant["sku"] for variant in product_variants}
    missing_skus = [sku for sku in prod_reference if sku not in found_skus]
    
    inventories = []
    result = None
    for variant in product_variants:
        for row in data_rows:
            publications = []
            if variant["sku"] == row["sku"]:
                inventory_item = variant["inventoryItem"]["id"]
                location_id = f"gid://shopify/Location/{row["id sede"]}"
                delta_quantity = row["qta"]
                sale_channels = row.get("canali di vendita", row.get("Canale di Vendita", ""))
                
                if sale_channels:
                    # Handle both comma-separated strings and single int values
                    if isinstance(sale_channels, int):
                        sale_channel_list = [str(sale_channels)]
                    elif isinstance(sale_channels, str):
                        sale_channel_list = [s.strip() for s in sale_channels.split(",") if s.strip()]
                    else:
                        sale_channel_list = []

                    for sale_channel in sale_channel_list:
                        publications.append({
                            "publicationId": f"gid://shopify/Publication/{sale_channel}"
                        })
                    
                    add_to_sale_channels(
                        resource_id=variant["product"]["id"],
                        channels=publications,
                    )
                set_activate_quantity_on_location(inventoryItemId=inventory_item, locationId=location_id)
                inventories.append({
                    "delta": delta_quantity, # quantità
                    "inventoryItemId": inventory_item,
                    "locationId": location_id
                })
        

    result = adjust_quantity_to_variant(inventories=inventories)
    
    return result, missing_skus