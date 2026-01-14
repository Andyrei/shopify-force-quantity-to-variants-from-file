import os
import shopify
import json
import toml
from pathlib import Path
from datetime import datetime
from datetime import datetime
from shopify.base import ShopifyConnection

"""
RESOURCE -> https://github.com/Shopify/shopify_python_api
"""

# Load config once at module level
PROJECT_ROOT = Path(__file__).parent.parent.parent
config = toml.load(PROJECT_ROOT / "config_stores.toml")

def get_store_credentials(store_id: str = None) -> dict:
    """
    Get store credentials from config based on store_id.
    Falls back to environment variables if store_id is not provided.
    """
    if store_id:
        stores = config.get("stores", {})
        if store_id in stores:
            store_config = stores[store_id]
            return {
                "access_token": store_config.get("ACCESS_TOKEN"),
                "base_url": f"{store_config.get('STORE_NAME')}.myshopify.com",
                "api_version": store_config.get("API_VERSION", "2025-04")
            }
    
    # Fallback to environment variables
    access_token = os.environ.get("ACCESS_TOKEN")
    store_name = os.environ.get("STORE_NAME")
    if access_token and store_name:
        return {
            "access_token": access_token,
            "base_url": f"{store_name}.myshopify.com",
            "api_version": os.environ.get("API_VERSION", "2025-04")
        }
    
    return None

def shopify_connection(credentials: dict = None, store_id: str = None) -> tuple[shopify.Session | None, float]:
    """
        Connect to Shopify API using the provided credentials.
        :param credentials: dict: The credentials for the Shopify API.
        :param store_id: str: The store ID from config (e.g., 'murphy', 'refrigiwear')
        :return:
            - shopify session: The Shopify API client.
            - float: The time taken to establish the connection.
    """
    if credentials:    
        # Extract credentials from the dictionary
        access_token = credentials["access_token"] if "access_token" in credentials else None
        base_url = credentials["base_url"] if "base_url" in credentials else None
        api_version = credentials.get("api_version", "2025-04")
    else:
        # Get credentials from config or environment
        creds = get_store_credentials(store_id)
        if not creds:
            return None
        access_token = creds["access_token"]
        base_url = creds["base_url"]
        api_version = creds["api_version"]

    if not access_token or not base_url:
        return None

    try:
        # Initialize the Shopify session
        session = shopify.Session(base_url, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)

        return shopify

    except KeyError as e:
        print(f"Error: {e}")
        return None


def shopify_query_graph(query: str=None, operation_name: str=None, variables: dict|None = None, store_id: str = None) -> dict:
    """
        Execute a GraphQL query against the Shopify API.
        :param query: str: the graphql query if operation file is missing
        :param operation_name: str: The name of the GraphQL operation. Must match the name in the GraphQL file.
        :param variables: dict: The variables for the GraphQL query. Default is None.
        :param store_id: str: The store ID from config to use for the connection.

        :return: dict: The response from the Shopify API.
    """
    if not query and not operation_name:
        return{"error": "Missing parameters"}
    
    shopify_session = shopify_connection(store_id=store_id)
    
    if shopify_session is None:
        print("ERROR: Failed to establish Shopify connection")
        print(f"DEBUG: store_id: {store_id}")
        return {"error": "Failed to establish Shopify connection. Check store configuration."}
    
    if query is None and operation_name:
        gql_query_path = Path(f"{operation_name}.graphql")
        if gql_query_path.exists():
            gql_query_doc = gql_query_path.read_text()
            response = shopify_session.GraphQL().execute(
                query=gql_query_doc,
                variables=variables,
                operation_name=operation_name,
            )
        else:
            return {"error": f"GraphQL file '{operation_name}.graphql' not found."}
    elif query:
        response = shopify_session.GraphQL().execute(
            query=query,
            variables=variables,
            operation_name=operation_name
        )
    else:
        return {"error": "No query or operation_name provided."}

    res = json.loads(response)

    # Check if the request was successful
    if res.get("errors"):
        return {"errors": res["errors"]}

    for value in res["data"].values():
        if isinstance(value, dict) and "userErrors" in value and value["userErrors"]:
            return {"errors": value["userErrors"]}

    return res["data"]


def check_product_exists(shopify_session: ShopifyConnection, channel_reference: str, product_reference: str) -> tuple[bool, float]:
    """
        Check if product exists in Shopify.
        :param shopify_session: ShopifyConnection: The Shopify API client.
        :param channel_reference: RetrieveProductDb: The product id to check.
        :param product_reference: str: The product reference (SKU).
        :return: bool: True if the product exists, False otherwise.
    """
    start_time = datetime.now()

    # Logic to check if the product exists in Shopify
    exists = False  # Placeholder for actual existence check logic

    result = shopify_query_graph(
            shopify_session=shopify_session,
            operation_name="CheckProductExists",
            variables={
                "query": f"barcode:{product_reference} AND id:{channel_reference}"
            }
    )

    time_elapsed = (datetime.now() - start_time).total_seconds()
    if result.get("errors"):
        print(f"Error checking product existence: {result.get('errors')}")
        return exists, time_elapsed

    if not result.get("data") and result.get("data").get("products"):
        exists = False

    exists = True
    return exists, time_elapsed

def get_product_variants_by_sku(sku_list: list, store_id: str = None) -> list[dict]:
    gql_query="""#gql
        query GetProductVariantBySku($query: String!, $after: String) {
            productVariants(first: 250, query: $query, after: $after) {
                nodes {
                    id
                    title
                    sku
                    barcode
                    product{
                        id
                    }
                    inventoryItem {
                        id
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    """
    # Build the query string for one or multiple SKUs
    if len(sku_list) == 1:
        query_str = f"sku:{sku_list[0]}"
    else:
        query_str = " OR ".join([f"sku:{s}" for s in sku_list])

    all_variants = []
    has_next_page = True
    cursor = None
    
    while has_next_page:
        gql_variables = {
            "query": query_str,
            "after": cursor
        }
        
        result = shopify_query_graph(
                query=gql_query,
                operation_name="GetProductVariantBySku",
                variables=gql_variables,
                store_id=store_id
        )
        
        if "error" in result:
            print(f"ERROR in get_product_variants_by_sku: {result['error']}")
            return None
        
        if "errors" in result:
            return None
            
        if result and "productVariants" in result:
            variants = result["productVariants"]["nodes"]
            all_variants.extend(variants)
            
            page_info = result["productVariants"]["pageInfo"]
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")
            
            print(f"DEBUG: Fetched {len(variants)} variants, total so far: {len(all_variants)}")
        else:
            break
    
    return all_variants

def detect_identifier_type(identifiers: list) -> str:
    """
    Detect whether a list of identifiers are SKUs or barcodes.
    
    :param identifiers: List of product identifiers
    :return: "barcode" if most valid identifiers are numeric, "sku" otherwise
    """
    if not identifiers:
        return "sku"  # Default to SKU if empty list
    
    # Filter out empty/invalid identifiers for detection
    valid_identifiers = [str(i) for i in identifiers if i and str(i) not in ["EMPTY_SKU", "nan", "None"]]
    
    if not valid_identifiers:
        return "sku"  # No valid identifiers, default to SKU
    
    # Count how many are purely numeric
    numeric_count = sum(1 for identifier in valid_identifiers if identifier.isdigit())
    
    # If more than 80% are numeric, treat as barcodes
    if numeric_count / len(valid_identifiers) > 0.8:
        return "barcode"
    else:
        return "sku"

def get_product_variants_by_identifier(identifier_list: list, identifier_type: str = "auto", store_id: str = None) -> list[dict]:
    """
    Get product variants by SKU or barcode with automatic detection or explicit type.
    
    :param identifier_list: List of SKUs or barcodes to search for
    :param identifier_type: Type of identifier - "sku", "barcode", or "auto" for automatic detection
    :param store_id: The store ID from config
    :return: List of product variant nodes
    """
    if not identifier_list:
        return []
    
    # Auto-detect identifier type if not specified
    if identifier_type == "auto":
        identifier_type = detect_identifier_type(identifier_list)
        print(f"DEBUG: Auto-detected identifier type: {identifier_type}")
    
    print(f"DEBUG: Searching for {len(identifier_list)} {identifier_type}s")
    
    # Use the appropriate function based on identifier type
    if identifier_type == "barcode":
        return get_product_variants_by_barcode(identifier_list, store_id=store_id)
    elif identifier_type == "sku":
        return get_product_variants_by_sku(identifier_list, store_id=store_id)
    else:
        raise ValueError(f"Invalid identifier_type: {identifier_type}. Must be 'sku', 'barcode', or 'auto'")

def get_product_variants_by_barcode(barcode_list: list, store_id: str = None) -> list[dict]:
    gql_query="""#gql
        query GetProductVariantByBarcode($query: String!, $after: String) {
            productVariants(first: 250, query: $query, after: $after) {
                nodes {
                    id
                    title
                    sku
                    barcode
                    product{
                        id
                    }
                    inventoryItem {
                        id
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    """
    # Build the query string for one or multiple SKUs
    if len(barcode_list) == 1:
        query_str = f"barcode:{barcode_list[0]}"
    else:
        query_str = " OR ".join([f"barcode:{b}" for b in barcode_list])

    all_variants = []
    has_next_page = True
    cursor = None
    
    while has_next_page:
        gql_variables = {
            "query": query_str,
            "after": cursor
        }
        
        result = shopify_query_graph(
                query=gql_query,
                operation_name="GetProductVariantByBarcode",
                variables=gql_variables,
                store_id=store_id
        )
        
        if "error" in result:
            print(f"ERROR in get_product_variants_by_barcode: {result['error']}")
            return None
        
        if "errors" in result:
            return None
            
        if result and "productVariants" in result:
            variants = result["productVariants"]["nodes"]
            all_variants.extend(variants)
            
            page_info = result["productVariants"]["pageInfo"]
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")
            
            print(f"DEBUG: Fetched {len(variants)} variants, total so far: {len(all_variants)}")
        else:
            break
    
    return all_variants

def set_activate_quantity_on_location(inventoryItemId: str, locationId: str, store_id: str = None):
    gql_query = """#gql
        mutation ActivateInventoryItem($inventoryItemId: ID!, $locationId: ID!, $available: Int) {
            inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId, available: $available) {
                inventoryLevel {
                    id
                    quantities(names: ["available"]) {
                        name
                        quantity
                    }
                    item {
                        id
                    }
                    location {
                        id
                    }
                }
            }
        }
    """
    
    gql_variables = {
       "inventoryItemId": inventoryItemId,
       "locationId": locationId,
       "available": 0
    }
    
    result = shopify_query_graph(
            query=gql_query,
            operation_name="ActivateInventoryItem",
            variables=gql_variables,
            store_id=store_id
    )
    
    return result

def adjust_quantity_to_variant(inventories: list[dict], store_id: str = None):
    """
        inventories: [{
            "delta": 2, # quantità
            "inventoryItemId": "gid://shopify/InventoryItem/56119140876579",
            "locationId": "gid://shopify/Location/105539928355"
        }]
        
        Shopify limits to 250 inventory changes per mutation, so we batch them.
    """
    gql_query="""#gql
        mutation inventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
            inventoryAdjustQuantities(input: $input) {
                inventoryAdjustmentGroup {
                    createdAt
                    reason
                    referenceDocumentUri
                    changes(quantityNames: ["available"]) {
                        name
                        delta
                        location{
                            id
                            name
                        }
                        item {
                           inventoryLevels(first: 50){
                               nodes{
                                   location {
                                       id
                                       name
                                   }
                                   quantities(names: ["available"]){
                                       name
                                       quantity
                                   }
                               }
                           }
                            variant {
                                availableForSale
                                displayName
                                product {
                                    id
                                    handle
                                }
                            }
                        }
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
    """
    
    # Batch inventories into chunks of 250 (Shopify's limit)
    BATCH_SIZE = 250
    all_results = []
    total_batches = (len(inventories) + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"DEBUG: Adjusting {len(inventories)} inventories in {total_batches} batch(es)")
    
    for i in range(0, len(inventories), BATCH_SIZE):
        batch = inventories[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        
        print(f"DEBUG: Processing batch {batch_num}/{total_batches} with {len(batch)} items")
        
        gql_variables = {
            "input": {
                "reason": "other",
                "name": "available",
                "changes": batch
            }
        }
        
        result = shopify_query_graph(
                query=gql_query,
                operation_name="inventoryAdjustQuantities",
                variables=gql_variables,
                store_id=store_id
        )
        
        # Check for errors in this batch
        if result and "errors" in result:
            print(f"ERROR in batch {batch_num}: {result['errors']}")
            return {"error": f"Failed at batch {batch_num}/{total_batches}", "details": result}
        
        if result and "inventoryAdjustQuantities" in result and result["inventoryAdjustQuantities"].get("userErrors"):
            print(f"USER ERRORS in batch {batch_num}: {result['inventoryAdjustQuantities']['userErrors']}")
            return {"error": f"User errors in batch {batch_num}/{total_batches}", "details": result}
        
        all_results.append(result)
    
    # Return the combined results (or just the last one for simplicity)
    # You could merge all changes if needed
    print(f"DEBUG: Successfully processed all {total_batches} batch(es)")
    
    # Merge all results into one response
    if all_results:
        merged_result = {
            "inventoryAdjustQuantities": {
                "inventoryAdjustmentGroup": {
                    "changes": []
                }
            }
        }
        
        for result in all_results:
            if result and "inventoryAdjustQuantities" in result:
                changes = result["inventoryAdjustQuantities"].get("inventoryAdjustmentGroup", {}).get("changes", [])
                merged_result["inventoryAdjustQuantities"]["inventoryAdjustmentGroup"]["changes"].extend(changes)
        
        # Copy metadata from the last result
        if all_results[-1] and "inventoryAdjustQuantities" in all_results[-1]:
            last_group = all_results[-1]["inventoryAdjustQuantities"]["inventoryAdjustmentGroup"]
            merged_result["inventoryAdjustQuantities"]["inventoryAdjustmentGroup"].update({
                "createdAt": last_group.get("createdAt"),
                "reason": last_group.get("reason"),
                "referenceDocumentUri": last_group.get("referenceDocumentUri")
            })
        
        return merged_result
    
    return None

def set_fixed_quantity_to_variant(inventories: list[dict], store_id: str = None):
    """ 
        Set fixed quantities to variants in Shopify.
        PAYLOAD EXAMPLE:
        {
            "input": {
                "name": "available",
                "reason": "correction",
                "referenceDocumentUri": "logistics://some.warehouse/take/2023-01-23T13:14:15Z",
                "quantities": [
                    {
                        "inventoryItemId": "gid://shopify/InventoryItem/30322695",
                        "locationId": "gid://shopify/Location/124656943",
                        "quantity": 11,
                    }
                ]
            }
        }
    """
    gql_query="""#gql
        mutation InventorySet($input: InventorySetQuantitiesInput!) {
            inventorySetQuantities(input: $input) {
                inventoryAdjustmentGroup {
                    createdAt
                    reason
                    referenceDocumentUri
                    changes {
                        name
                        delta
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
    """
    # Batch inventories into chunks of 250 (Shopify's limit)
    BATCH_SIZE = 250
    all_results = []
    total_batches = (len(inventories) + BATCH_SIZE - 1) // BATCH_SIZE
    
    for i in range(0, len(inventories), BATCH_SIZE):
        batch = inventories[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        
        print(f"DEBUG: Processing batch {batch_num}/{total_batches} with {len(batch)} items")
        
        gql_variables = {
            "input": {
                "name": "available",
                "reason": "correction",
                "ignoreCompareQuantity": True,
                "quantities": batch
            }
        }
        
        result = shopify_query_graph(
                query=gql_query,
                operation_name="InventorySet",
                variables=gql_variables,
                store_id=store_id
        )
        
        # Check for errors in this batch
        if result and "errors" in result:
            print(f"ERROR in batch {batch_num}: {result['errors']}")
            return {"error": f"Failed at batch {batch_num}/{total_batches}", "details": result}
        
        if result and "inventorySetQuantities" in result and result["inventorySetQuantities"].get("userErrors"):
            print(f"USER ERRORS in batch {batch_num}: {result['inventorySetQuantities']['userErrors']}")
            return {"error": f"User errors in batch {batch_num}/{total_batches}", "details": result}
        
        all_results.append(result)
    
    # Return the combined results (or just the last one for simplicity)
    # You could merge all changes if needed
    print(f"DEBUG: Successfully processed all {total_batches} batch(es)")
    
    # Merge all results into one response
    if all_results:
        merged_result = {
                "changes": [],
                "createdAt": None,
                "reason": None,
                "referenceDocumentUri": None
            }
        
        for result in all_results:
            if result and "inventorySetQuantities" in result and result["inventorySetQuantities"].get("inventoryAdjustmentGroup") is not None:
                changes = result["inventorySetQuantities"].get("inventoryAdjustmentGroup", {}).get("changes", [])
                merged_result["changes"].extend(changes)
            else:
                print("DEBUG: No inventoryAdjustmentGroup found in result")
        
        # Copy metadata from the last result
        if all_results[-1] and "inventorySetQuantities" in all_results[-1]:
            last_group = all_results[-1]["inventorySetQuantities"]["inventoryAdjustmentGroup"]
            merged_result.update({
                "createdAt": last_group.get("createdAt"),
                "reason": last_group.get("reason"),
                "referenceDocumentUri": last_group.get("referenceDocumentUri")
            })
        
        return merged_result
    
    return None
    

def add_to_sale_channels(resource_id: object, channels: list[dict], store_id: str = None) -> dict | None:
    """
    Adds products to sale channels in Shopify.

    :param shopify: The Shopify session object.
    :param resource_id: The ID of the resource to be added to the sale channel.
    :param channels: List of dictionaries containing product IDs and sale channel IDs.
    :param store_id: The store ID from config

    :return: Response from the Shopify API or None if an error occurs.

    Example resource_input:
        {
         "resource_id": "gid://shopify/Product/9834861953315",
         "channels": [
               {
                   "publicationId": "gid://shopify/Publication/240302129443"
               },
               {
                   "publicationId": "gid://shopify/Publication/240302326051"
               }
           ]
        }
    """
    
    gql_query = """#gql
        mutation SetObjectToSaleChannel($resource_id: ID!, $channels: [PublicationInput!]!) {
            publishablePublish(id: $resource_id input: $channels) {
                publishable {
                    resourcePublications(first:10){
                        nodes{
                            isPublished
                        }
                    }
                }
                userErrors {
                field
                message
                }
            }
        }
    """
    res = shopify_query_graph(
        query=gql_query,
        operation_name="SetObjectToSaleChannel",
        variables={"resource_id": resource_id, "channels": channels},
        store_id=store_id
    )

    return res