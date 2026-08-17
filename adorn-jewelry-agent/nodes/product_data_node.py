import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "product_data.json")

def load_products():
    with open(DATA_PATH, "r") as f:
        data = json.load(f)
    return data
def product_node(State) -> dict:
    products = load_products()
    return {"product_data": products}