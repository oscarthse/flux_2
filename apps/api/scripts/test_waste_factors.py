"""Test AI-generated waste factors"""
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

print("=" * 80)
print("WASTE FACTOR AI GENERATION TEST")
print("=" * 80)

# Get recipe estimates (will trigger AI generation)
response = requests.get(
    "http://localhost:8000/api/recipes/menu-items/estimates",
    headers=headers
)

print(f"\nStatus: {response.status_code}\n")

if response.status_code == 200:
    result = response.json()
    print(f"Generated {result['total']} recipes with waste factors\n")

    for item in result['items']:
        print(f"\n{'='*80}")
        print(f"{item['menu_item_name']} - ${item.get('menu_item_price', 'N/A')}")
        print(f"{'='*80}")
        print(f"Confidence: {item['confidence']}")
        if item.get('estimation_notes'):
            print(f"Notes: {item['estimation_notes']}")

        print(f"\n{'Ingredient':<30} {'Qty':<8} {'Base $':<10} {'Waste%':<8} {'Total $':<10} {'Category':<12} {'Fresh'}")
        print("-" * 105)

        base_total = 0
        waste_total = 0
        total_cost = 0

        for ing in item['ingredients']:
            base = float(ing['base_cost'])
            waste_pct = float(ing['waste_factor']) * 100
            total = float(ing['estimated_cost'])
            waste_cost = total - base

            base_total += base
            waste_total += waste_cost
            total_cost += total

            print(f"{ing['name']:<30} {ing['quantity']}{ing['unit']:<7} "
                  f"${base:<9.2f} {waste_pct:<7.1f}% "
                  f"${total:<9.2f} {ing.get('category', 'N/A'):<12} "
                  f"{ing.get('perishability', 'N/A')}")

        print("-" * 105)
        print(f"{'TOTALS':<30} {'':<8} ${base_total:<9.2f} "
              f"{(waste_total/base_total*100 if base_total > 0 else 0):<7.1f}% "
              f"${total_cost:<9.2f}")

        if item.get('menu_item_price'):
            price = float(item['menu_item_price'])
            margin_without_waste = ((price - base_total) / price * 100) if price > 0 else 0
            margin_with_waste = ((price - total_cost) / price * 100) if price > 0 else 0
            hidden_cost_impact = margin_without_waste - margin_with_waste

            print(f"\n📊 MARGIN ANALYSIS:")
            print(f"   Margin without waste: {margin_without_waste:.1f}%")
            print(f"   Margin with waste:    {margin_with_waste:.1f}%")
            print(f"   Hidden cost impact:   -{hidden_cost_impact:.1f}% (${waste_total:.2f} waste)")

else:
    print(f"Error: {response.text}")
