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
                "query": f"sku:{product_reference} AND id:{channel_reference}"
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

def get_product_variants_by_sku(sku_list: list ) -> tuple[dict]:
    gql_query="""#gql
        query GetProductVariantBySku($query: String!) {
            productVariants(first: 250, query: $query) {
                nodes {
                    id
                    title
                    sku
                    product{
                        id
                    }
                    inventoryItem {
                        id
                    }
                }
            }
        }
    """
    # Build the query string for one or multiple SKUs
    if len(sku_list) == 1:
        query_str = f"sku:{sku_list[0]}"
    else:
        query_str = " OR ".join([f"sku:{s}" for s in sku_list])


    gql_variables = {
        "query": query_str
    }
    
    result = shopify_query_graph(
            query=gql_query,
            operation_name="GetProductVariantBySku",
            variables=gql_variables
    )
    
    if not "errors" in result and result and result["productVariants"]["nodes"]:
        return result["productVariants"]["nodes"]
    
    return result

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