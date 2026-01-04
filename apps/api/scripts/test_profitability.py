"""Test the profitability endpoint with confirmed recipes"""
import requests
import json

# Login
login_response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "synthetic@example.com", "password": "test123"}
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.status_code}")
    print(login_response.text)
    exit(1)

token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("=" * 70)
print("PROFITABILITY TEST")
print("=" * 70)

# Get profitability data
response = requests.get(
    "http://localhost:8000/api/recipes/profitability",
    headers=headers
)

print(f"\nStatus: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    print(f"\nAverage Margin: {result['average_margin']}%")
    print(f"Low Margin Count: {result['low_margin_count']}")
    print(f"\nMenu Items ({len(result['items'])}):\n")

    for item in result['items']:
        print(f"{item['menu_item_name']}")
        print(f"  Price: ${float(item['menu_item_price']):.2f}")
        print(f"  COGS: ${float(item['total_cogs']):.2f}")
        print(f"  Margin: {float(item['margin_percentage']):.1f}%")
        print(f"  Recipe Source: {item['recipe_source']}")
        print(f"  BCG Quadrant: {item.get('bcg_quadrant', 'N/A')}")

        if item.get('ingredient_breakdown'):
            print(f"  Ingredients:")
            for ing in item['ingredient_breakdown']:
                print(f"    - {ing['quantity']}{ing['unit']} {ing['ingredient_name']}: ${float(ing['waste_adjusted_cost']):.2f}")
        print()
else:
    print(f"Error: {response.text}")
