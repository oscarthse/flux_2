"""Check profitability API response structure"""
import requests
import json

# Login
login_response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "synthetic@example.com", "password": "test123"}
)

token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Get profitability data
response = requests.get(
    "http://localhost:8000/api/recipes/profitability",
    headers=headers
)

if response.status_code == 200:
    result = response.json()

    print("=" * 80)
    print("PROFITABILITY API RESPONSE STRUCTURE")
    print("=" * 80)
    print(f"\nTop-level keys: {list(result.keys())}")
    print(f"Number of items: {len(result.get('items', []))}")

    if result.get('items'):
        print("\n" + "=" * 80)
        print("FIRST ITEM STRUCTURE:")
        print("=" * 80)
        first_item = result['items'][0]
        print(json.dumps(first_item, indent=2, default=str))

        print("\n" + "=" * 80)
        print("INGREDIENT BREAKDOWN STRUCTURE:")
        print("=" * 80)
        if first_item.get('ingredient_breakdown'):
            print(json.dumps(first_item['ingredient_breakdown'][0], indent=2, default=str))
else:
    print(f"Error: {response.status_code}")
    print(response.text)
