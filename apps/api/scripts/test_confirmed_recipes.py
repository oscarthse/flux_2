"""Test the confirmed recipes endpoint"""
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
print("CONFIRMED RECIPES TEST")
print("=" * 70)

# Get confirmed recipes
response = requests.get(
    "http://localhost:8000/api/recipes/menu-items/confirmed",
    headers=headers
)

print(f"\nStatus: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    print(f"Found {result['total']} confirmed recipes\n")

    if result['items']:
        for item in result['items']:
            print(f"\n{item['menu_item_name']}")
            print(f"  Price: ${item.get('menu_item_price', 'N/A')}")
            print(f"  Total Cost: ${item['total_estimated_cost']}")
            print(f"  Confidence: {item['confidence']}")

            if item['menu_item_price']:
                margin = ((float(item['menu_item_price']) - float(item['total_estimated_cost'])) / float(item['menu_item_price'])) * 100
                print(f"  Margin: {margin:.1f}%")

            print(f"  Ingredients:")
            for ing in item['ingredients']:
                print(f"    - {ing['quantity']}{ing['unit']} {ing['name']}: ${ing['estimated_cost']}")
    else:
        print("No confirmed recipes yet")
else:
    print(f"Error: {response.text}")
