"""Test the recipe confirmation workflow"""
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
print("STEP 1: Get unconfirmed recipe estimates")
print("=" * 70)

response = requests.get(
    "http://localhost:8000/api/recipes/menu-items/estimates",
    headers=headers
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print(f"Found {result['total']} unconfirmed recipes")

    if result['items']:
        # Pick the first item to confirm
        item = result['items'][0]
        print(f"\nItem to confirm: {item['menu_item_name']}")
        print(f"Current cost: ${item['total_estimated_cost']}")
        print(f"Ingredients: {len(item['ingredients'])}")

        print("\n" + "=" * 70)
        print("STEP 2: Save/confirm the recipe")
        print("=" * 70)

        # Modify an ingredient slightly to test user edit
        ingredients = item['ingredients']
        if ingredients:
            ingredients[0]['estimated_cost'] = float(ingredients[0]['estimated_cost']) + 0.10
            print(f"Modified first ingredient cost by +$0.10")

        save_response = requests.post(
            f"http://localhost:8000/api/recipes/menu-items/{item['menu_item_id']}/save-recipe",
            headers=headers,
            json={"ingredients": ingredients}
        )

        print(f"Status: {save_response.status_code}")
        if save_response.status_code == 200:
            save_result = save_response.json()
            print(f"Response: {json.dumps(save_result, indent=2)}")
        else:
            print(f"Error: {save_response.text}")

        print("\n" + "=" * 70)
        print("STEP 3: Check if recipe is removed from unconfirmed list")
        print("=" * 70)

        response2 = requests.get(
            "http://localhost:8000/api/recipes/menu-items/estimates",
            headers=headers
        )

        print(f"Status: {response2.status_code}")
        if response2.status_code == 200:
            result2 = response2.json()
            print(f"Now found {result2['total']} unconfirmed recipes (should be {result['total'] - 1})")

            # Check if the confirmed item is gone
            confirmed_id = item['menu_item_id']
            still_in_list = any(i['menu_item_id'] == confirmed_id for i in result2['items'])

            if still_in_list:
                print(f"❌ FAILED: {item['menu_item_name']} is still in unconfirmed list!")
            else:
                print(f"✅ SUCCESS: {item['menu_item_name']} removed from unconfirmed list!")
        else:
            print(f"Error: {response2.text}")
    else:
        print("No unconfirmed recipes found to test with")
else:
    print(f"Error: {response.text}")
