"""Test the new recipe estimates API endpoint"""
import requests
import json

# Login
login_response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "synthetic@example.com", "password": "test123"}
)
token = login_response.json()["access_token"]

# Get recipe estimates
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8000/api/recipes/menu-items/estimates",
    headers=headers
)

print("Status:", response.status_code)
print("\nResponse:")
result = response.json()
print(json.dumps(result, indent=2, default=str))

# Print summary
if result.get("items"):
    print("\n" + "="*70)
    print("RECIPE ESTIMATES SUMMARY")
    print("="*70)
    for item in result["items"]:
        print(f"\n{item['menu_item_name']} (Price: ${item.get('menu_item_price', 'N/A')})")
        print(f"  Total Cost: ${item['total_estimated_cost']}")
        print(f"  Confidence: {item['confidence']}")
        print(f"  Ingredients:")
        for ing in item["ingredients"]:
            print(f"    - {ing['quantity']}{ing['unit']} {ing['name']}: ${ing['estimated_cost']}")
