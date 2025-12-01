from app.utilities.shopify import (
    add_to_sale_channels, 
    adjust_quantity_to_variant, 
    get_product_variants_by_identifier, 
    set_activate_quantity_on_location,
    detect_identifier_type
)


def get_product_variants_and_sync(data_rows, store_id: str = None) -> list[dict, list, list, list]:
    
    print(f"DEBUG: Starting sync with {len(data_rows)} rows for store: {store_id}")
    
    prod_reference = []
    
    for row in data_rows:
        # Use 'barcode' if it exists, otherwise use 'sku'
        # Convert to string to ensure consistent data types
        if "barcode" in row:
            prod_reference.append(str(row["barcode"]))
        else:
            prod_reference.append(str(row["sku"]))

    print(f"DEBUG: Extracted {len(prod_reference)} references")
    print(f"DEBUG: Unique references: {len(set(prod_reference))}")
    print(f"DEBUG: Duplicate references in file: {len(prod_reference) - len(set(prod_reference))}")
    print(f"DEBUG: Sample references: {prod_reference[:3] if prod_reference else 'None'}")

    # Determine identifier type - prioritize explicit field presence, fallback to auto-detection
    use_barcode = "barcode" in data_rows[0]
    if use_barcode:
        identifier_type = "barcode"
    else:
        # Auto-detect based on content if SKU field is present
        identifier_type = detect_identifier_type(prod_reference)
    
    print(f"DEBUG: Using {identifier_type} search (field-based: {use_barcode})")
    product_variants = get_product_variants_by_identifier(prod_reference, identifier_type, store_id=store_id)
    
    print(f"DEBUG: Found {len(product_variants) if product_variants else 0} variants from Shopify")
    
    if not product_variants:
        print("DEBUG: No variants found, returning early")
        return [], prod_reference, [], []
    
    # Create a mapping of variants by their reference (barcode or sku)
    variant_map = {}
    found_refs = set()
    
    for variant in product_variants:
        if identifier_type == "barcode":
            ref = variant.get("barcode")
        else:  # identifier_type == "sku"
            ref = variant.get("sku")
        
        if ref:
            # Ensure consistent string type
            ref = str(ref)
            variant_map[ref] = variant
            found_refs.add(ref)
    
    # Find missing rows and duplicate rows separately
    missing_rows = []
    duplicate_rows = []
    seen_refs = {}
    
    for i, row in enumerate(data_rows):
        if identifier_type == "barcode":
            row_ref = str(row.get("barcode"))
        else:
            row_ref = str(row.get("sku"))
        
        if row_ref not in found_refs and row_ref not in missing_rows:
            # This SKU doesn't exist in Shopify
            missing_rows.append(row["sku"] if "sku" in row else row["barcode"])
        elif row_ref in seen_refs and row_ref not in duplicate_rows:
            # This SKU was already processed - it's a duplicate in the file
            duplicate_rows.append(row["sku"] if "sku" in row else row["barcode"])
        else:
            # First occurrence of this SKU
            seen_refs[row_ref] = i
    
    print(f"DEBUG: prod_reference types: {[type(ref).__name__ for ref in prod_reference[:3]]}")
    print(f"DEBUG: found_refs types: {[type(ref).__name__ for ref in list(found_refs)[:3]]}")
    print(f"DEBUG: Missing rows: {len(missing_rows)}")
    print(f"DEBUG: Duplicate rows: {len(duplicate_rows)}")
    print(f"DEBUG: Missing unique SKUs: {len(set(prod_reference) - found_refs)}")
    print(f"DEBUG: Found references: {len(found_refs)}")
    
    inventories = []
    result = None
    
    # Process each row and match with variants efficiently
    for row in data_rows:
        # Convert to string to ensure consistent data types
        if identifier_type == "barcode":
            row_ref = str(row.get("barcode"))
        else:  # identifier_type == "sku"
            row_ref = str(row.get("sku"))
        
        if row_ref in variant_map:
            variant = variant_map[row_ref]
            publications = []
            
            inventory_item = variant["inventoryItem"]["id"]
            
            # Get location ID from the row (file should have this data now, all lowercase)
            row_location_id = row.get("id sede") or row.get("location_id") or row.get("location")
            if row_location_id:
                location_id_full = f"gid://shopify/Location/{row_location_id}"
            else:
                print(f"WARNING: No location ID found for row {row_ref}")
                continue
            
            delta_quantity = row["qta"]
            
            # Get sale channel from the row (file should have this data now, all lowercase)
            row_sale_channel = row.get("canali di vendita") or row.get("canale di vendita") or row.get("sale_channel")
            if row_sale_channel:
                sale_channels_value = row_sale_channel
            else:
                print(f"WARNING: No sale channel found for row {row_ref}")
                sale_channels_value = ""
            
            if sale_channels_value:
                # Handle both comma-separated strings and single int values
                if isinstance(sale_channels_value, int):
                    sale_channel_list = [str(sale_channels_value)]
                elif isinstance(sale_channels_value, str):
                    sale_channel_list = [s.strip() for s in sale_channels_value.split(",") if s.strip()]
                else:
                    sale_channel_list = []

                for sale_channel_item in sale_channel_list:
                    publications.append({
                        "publicationId": f"gid://shopify/Publication/{sale_channel_item}"
                    })
                    
            # Only execute Shopify operations if no variants are missing
            if not missing_rows:
                if publications:
                    add_to_sale_channels(
                        resource_id=variant["product"]["id"],
                        channels=publications,
                        store_id=store_id
                    )
                set_activate_quantity_on_location(inventoryItemId=inventory_item, locationId=location_id_full, store_id=store_id)
                inventories.append({
                    "delta": delta_quantity, # quantità
                    "inventoryItemId": inventory_item,
                    "locationId": location_id_full
                })
        

    # Only adjust quantities if no variants are missing
    if not missing_rows and inventories:
        result = adjust_quantity_to_variant(inventories=inventories, store_id=store_id)
    
    return result, missing_rows, duplicate_rows, found_refs