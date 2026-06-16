import requests
import json
import os
from datetime import datetime

URL = "https://fakestoreapi.com/products"
response = requests.get(URL)
products = response.json()

now = datetime.now().isoformat()

# ── Step 1: Build Category fixture ───────────────────────────────
# FakeStore API has these categories:
#   "men's clothing", "women's clothing",
#   "jewelery", "electronics"
# We map them to clean slugs

CATEGORY_MAP = {
    "men's clothing":   {"id": 1, "name": "Men's Clothing",   "slug": "mens-clothing"},
    "women's clothing": {"id": 2, "name": "Women's Clothing", "slug": "womens-clothing"},
    "jewelery":         {"id": 3, "name": "Jewellery",        "slug": "jewellery"},
    "electronics":      {"id": 4, "name": "Electronics",      "slug": "electronics"},
}

category_fixture = []
for api_name, data in CATEGORY_MAP.items():
    category_fixture.append({
        "model": "store.category",
        "pk": data["id"],
        "fields": {
            "name": data["name"],
            "slug": data["slug"],
            "description": "",
            "created_at": now,
        }
    })

# ── Step 2: Build Product fixture ────────────────────────────────
product_fixture = []

for i, product in enumerate(products, start=1):
    api_category = product.get("category", "")
    category_data = CATEGORY_MAP.get(api_category)
    category_id = category_data["id"] if category_data else None

    product_fixture.append({
        "model": "store.product",
        "pk": i,
        "fields": {
            "title": product["title"],
            "price": product["price"],
            "description": product["description"],
            "image": product["image"],
            "stock": 50 , # default stock,
            "reserved_stock": 0,    # ← new field
            "category": category_id,    # ← new field (FK)
            "created_at": now,
        }
    })

# ── Step 3: Write fixtures ────────────────────────────────────────
os.makedirs("store/fixtures", exist_ok=True)

# Write categories first
with open("store/fixtures/categories.json", "w", encoding="utf-8") as f:
    json.dump(category_fixture, f, indent=4, ensure_ascii=False)

print(f"categories.json created - {len(category_fixture)} categories")

# Write products
with open("store/fixtures/products.json", "w", encoding="utf-8") as f:
    json.dump(product_fixture, f, indent=4, ensure_ascii=False)

print("products.json created successfully")