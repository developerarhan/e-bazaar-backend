import requests
import json
from datetime import datetime

URL = "https://fakestoreapi.com/products"
response = requests.get(URL)
products = response.json()

fixture_data = []
now = datetime.now().isoformat()

for i, product in enumerate(products, start=1):
    fixture_data.append({
        "model": "store.product",
        "pk": i,
        "fields": {
            "title": product["title"],
            "price": product["price"],
            "description": product["description"],
            "image": product["image"],
            "stock": 50 , # default stock,
            "created_at": now,
        }
    })

with open("fixtures/products.json", "w", encoding="utf-8") as f:
    json.dump(fixture_data, f, indent=4)

print("products.json created successfully")