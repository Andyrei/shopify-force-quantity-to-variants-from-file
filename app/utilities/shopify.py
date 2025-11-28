import os
import shopify
import json
from pathlib import Path
from datetime import datetime
from datetime import datetime
from shopify.base import ShopifyConnection

"""
RESOURCE -> https://github.com/Shopify/shopify_python_api
"""

def shopify_connection(credentials: dict = None) -> tuple[shopify.Session | None, float]:
    """
        Connect to Shopify API using the provided credentials.
        :param credentials: dict: The credentials for the Shopify API.
        :return:
            - shopify session: The Shopify API client.
            - float: The time taken to establish the connection.
    """
    if credentials:    
        # Extract credentials from the dictionary
        access_token = credentials["access_token"] if "access_token" in credentials else None
        base_url = credentials["base_url"] if "base_url" in credentials else None
    elif not credentials:
        access_token = os.environ.get("ACCESS_TOKEN")
        base_url = f"{os.environ.get("STORE_NAME")}.myshopify.com"

    if not access_token or not base_url:
        return None

    API_VERSION = '2025-04'
    try:
        # Initialize the Shopify session
        session = shopify.Session(base_url, API_VERSION, access_token)
        shopify.ShopifyResource.activate_session(session)

        return shopify

    except KeyError as e:
        print(f"Error: {e}")
        return None


def shopify_query_graph(query: str=None, operation_name: str=None, variables: dict|None = None, company_id: int = 1) -> dict:
    """
        Execute a GraphQL query against the Shopify API.
        :param shopify_session: shopify: The Shopify session object.
        :param query: str: the graphql query if operation file is missing
        :param operation_name: str: The name of the GraphQL operation. Must match the name in the GraphQL file.
        :param variables: dict: The variables for the GraphQL query. Default is None.
        :param company_id: int: The ID of the company. Default is 1.

        :return: dict: The response from the Shopify API.
    """
    if not query and not operation_name:
        return{"error": "Missing parameters"}
    
    shopify_session = shopify_connection()
    
    if shopify_session is None:
        print("ERROR: Failed to establish Shopify connection")
        print(f"DEBUG: ACCESS_TOKEN exists: {bool(os.environ.get('ACCESS_TOKEN'))}")
        print(f"DEBUG: STORE_NAME exists: {bool(os.environ.get('STORE_NAME'))}")
        return {"error": "Failed to establish Shopify connection. Check ACCESS_TOKEN and STORE_NAME environment variables."}
    
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

def get_product_variants_by_sku(sku_list: list ) -> list[dict]:
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
                variables=gql_variables
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
    :return: "barcode" if all identifiers are numeric, "sku" otherwise
    """
    if not identifiers:
        return "sku"  # Default to SKU if empty list
    
    str_identifiers = [str(identifier) for identifier in identifiers]
    return "barcode" if all(identifier.isdigit() for identifier in str_identifiers) else "sku"

def get_product_variants_by_identifier(identifier_list: list, identifier_type: str = "auto") -> list[dict]:
    """
    Get product variants by SKU or barcode with automatic detection or explicit type.
    
    :param identifier_list: List of SKUs or barcodes to search for
    :param identifier_type: Type of identifier - "sku", "barcode", or "auto" for automatic detection
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
        return get_product_variants_by_barcode(identifier_list)
    elif identifier_type == "sku":
        return get_product_variants_by_sku(identifier_list)
    else:
        raise ValueError(f"Invalid identifier_type: {identifier_type}. Must be 'sku', 'barcode', or 'auto'")

def get_product_variants_by_barcode(barcode_list: list ) -> list[dict]:
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
                variables=gql_variables
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

def set_activate_quantity_on_location(inventoryItemId: str, locationId: str):
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
            variables=gql_variables
    )
    
    return result

def adjust_quantity_to_variant(inventories: list[dict]):
    """
        inventories: [{
            "delta": 2, # quantità
            "inventoryItemId": "gid://shopify/InventoryItem/56119140876579",
            "locationId": "gid://shopify/Location/105539928355"
        }]
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
    
    gql_variables = {
        "input": {
            "reason": "other",
            "name": "available",
            "changes": inventories
        }
    }
    
    result = shopify_query_graph(
            query=gql_query,
            operation_name="inventoryAdjustQuantities",
            variables=gql_variables
    )
    
    return result



def add_to_sale_channels(resource_id: object, channels: list[dict]) -> dict | None:
    """
    Adds products to sale channels in Shopify.

    :param shopify: The Shopify session object.
    :param resource_id: The ID of the resource to be added to the sale channel.
    :param channels: List of dictionaries containing product IDs and sale channel IDs.

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
        variables={"resource_id": resource_id, "channels": channels}
    )

    return res