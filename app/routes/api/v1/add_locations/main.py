from collections import defaultdict
from unittest import result
from app.utilities.shopify import add_to_sale_channels, adjust_quantity_to_variant, get_product_variants_by_barcode, get_product_variants_by_sku, set_activate_quantity_on_location


def get_product_variants_and_sync(data_rows) -> list[dict, list, list]:
    
    print(f"DEBUG: Starting sync with {len(data_rows)} rows")
    
    prod_reference = []
    
    for row in data_rows:
        # Use 'barcode' if it exists, otherwise use 'sku'
        if "barcode" in row:
            prod_reference.append(row["barcode"])
        else:
            prod_reference.append(row["sku"])

    print(f"DEBUG: Extracted {len(prod_reference)} references")
    print(f"DEBUG: Sample references: {prod_reference[:3] if prod_reference else 'None'}")

    # Check if all references are SKU (alphanumeric) or barcode (numeric)
    if all(str(ref).isdigit() for ref in prod_reference):
        # All barcodes
        print("DEBUG: Using barcode search")
        product_variants = get_product_variants_by_barcode(prod_reference)
    else:
        # Assume all SKUs
        print("DEBUG: Using SKU search")
        product_variants = get_product_variants_by_sku(prod_reference)
    
    print(f"DEBUG: Found {len(product_variants) if product_variants else 0} variants from Shopify")
    
    if not product_variants:
        print("DEBUG: No variants found, returning early")
        return [], prod_reference, []
    
    # Create a mapping of variants by their reference (barcode or sku)
    use_barcode = "barcode" in data_rows[0]
    variant_map = {}
    found_refs = set()
    
    for variant in product_variants:
        if use_barcode:
            ref = variant.get("barcode")
            if ref:
                variant_map[ref] = variant
                found_refs.add(ref)
        else:
            ref = variant.get("sku")
            if ref:
                variant_map[ref] = variant
                found_refs.add(ref)
    
    # Find missing references
    missing_refs = [ref for ref in prod_reference if ref not in found_refs]
    
    inventories = []
    result = None
    
    # Process each row and match with variants efficiently
    for row in data_rows:
        row_ref = row.get("barcode") if use_barcode else row.get("sku")
        
        if row_ref in variant_map:
            variant = variant_map[row_ref]
            publications = []
            
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
                    
            # Only execute Shopify operations if no variants are missing
            if not missing_refs:
                if publications:
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
        

    # Only adjust quantities if no variants are missing
    if not missing_refs and inventories:
        result = adjust_quantity_to_variant(inventories=inventories)
    
    return result, missing_refs, found_refs