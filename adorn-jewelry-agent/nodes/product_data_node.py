import json

def load_products():
    with open("data/products.json", "r") as f:
        data = json.load(f)
    return data

def product_node(State) -> dict:
    products = load_products()
    return {"product_data": products}