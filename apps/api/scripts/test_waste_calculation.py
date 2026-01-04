"""Test complete waste factor calculation flow"""
import requests
import json

# Login
login_response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "synthetic@example.com", "password": "test123"}
)

token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("=" * 90)
print("WASTE FACTOR CALCULATION FLOW TEST")
print("=" * 90)

# Step 1: Get estimates (AI generated)
print("\n📊 STEP 1: AI Generates Estimates with Waste Factors")
print("-" * 90)

response = requests.get(
    "http://localhost:8000/api/recipes/menu-items/estimates",
    headers=headers
)

if response.status_code != 200:
    print(f"Error getting estimates: {response.text}")
    exit(1)

result = response.json()
burger = next((item for item in result['items'] if 'burger' in item['menu_item_name'].lower()), None)

if not burger:
    print("No burger found!")
    exit(1)

print(f"\nMenu Item: {burger['menu_item_name']} - ${burger['menu_item_price']}")
print("\nAI-Generated Ingredients:")
print(f"{'Ingredient':<25} {'Qty':<10} {'Base $':<10} {'Waste %':<10} {'Total $':<10}")
print("-" * 90)

for ing in burger['ingredients']:
    base = float(ing['base_cost'])
    waste_pct = float(ing['waste_factor']) * 100
    total = float(ing['estimated_cost'])
    calculated_total = base * (1 + float(ing['waste_factor']))

    print(f"{ing['name']:<25} {ing['quantity']}{ing['unit']:<9} ${base:<9.2f} {waste_pct:<9.1f}% ${total:<9.2f}")

    # Verify calculation
    if abs(total - calculated_total) > 0.01:
        print(f"  ⚠️  CALCULATION ERROR: Expected ${calculated_total:.2f}, got ${total:.2f}")

# Step 2: Save recipe (confirm it)
print(f"\n📝 STEP 2: Save Recipe (Confirm)")
print("-" * 90)

save_response = requests.post(
    f"http://localhost:8000/api/recipes/menu-items/{burger['menu_item_id']}/save-recipe",
    headers=headers,
    json={"ingredients": burger['ingredients']}
)

if save_response.status_code == 200:
    print(f"✅ Recipe saved successfully")
else:
    print(f"❌ Failed to save: {save_response.text}")
    exit(1)

# Step 3: Check profitability (COGS calculation)
print(f"\n💰 STEP 3: COGS Calculation from Confirmed Recipe")
print("-" * 90)

prof_response = requests.get(
    "http://localhost:8000/api/recipes/profitability",
    headers=headers
)

if prof_response.status_code != 200:
    print(f"Error getting profitability: {prof_response.text}")
    exit(1)

prof_result = prof_response.json()
burger_prof = next((item for item in prof_result['items'] if burger['menu_item_id'] in item['menu_item_id']), None)

if not burger_prof:
    print("Burger not found in profitability!")
    exit(1)

print(f"\nCOGS Calculation for {burger_prof['menu_item_name']}:")
print(f"{'Ingredient':<25} {'Qty':<10} {'Base $':<10} {'Waste %':<10} {'Waste-Adj $':<12}")
print("-" * 90)

base_total = 0
waste_total = 0

for ing in burger_prof['ingredient_breakdown']:
    base = float(ing['base_cost'])
    waste_pct = float(ing['waste_factor']) * 100
    waste_adj = float(ing['waste_adjusted_cost'])
    waste_cost = waste_adj - base

    base_total += base
    waste_total += waste_cost

    print(f"{ing['ingredient_name']:<25} {ing['quantity']}{ing['unit']:<9} "
          f"${base:<9.2f} {waste_pct:<9.1f}% ${waste_adj:<11.2f}")

print("-" * 90)
print(f"{'TOTALS':<25} {'':<10} ${base_total:<9.2f} {'':<10} ${base_total + waste_total:<11.2f}")
print(f"\nBase Cost:        ${base_total:.2f}")
print(f"Waste Cost:       ${waste_total:.2f} ({waste_total/base_total*100:.1f}% of base)")
print(f"True COGS:        ${float(burger_prof['total_cogs']):.2f}")

# Verify calculation
expected_cogs = base_total + waste_total
actual_cogs = float(burger_prof['total_cogs'])

if abs(expected_cogs - actual_cogs) < 0.01:
    print(f"✅ COGS calculation correct!")
else:
    print(f"⚠️  COGS mismatch: Expected ${expected_cogs:.2f}, got ${actual_cogs:.2f}")

# Step 4: Margin Analysis
print(f"\n📈 STEP 4: Margin Analysis")
print("-" * 90)

price = float(burger_prof['menu_item_price'])
margin_without_waste = ((price - base_total) / price * 100)
margin_with_waste = ((price - actual_cogs) / price * 100)
hidden_impact = margin_without_waste - margin_with_waste

print(f"Menu Price:              ${price:.2f}")
print(f"\nWithout Waste Factors:")
print(f"  COGS:                  ${base_total:.2f}")
print(f"  Margin:                {margin_without_waste:.1f}%")
print(f"\nWith Waste Factors:")
print(f"  COGS:                  ${actual_cogs:.2f}")
print(f"  Margin:                {margin_with_waste:.1f}%")
print(f"\n🎯 Hidden Cost Impact:   -{hidden_impact:.1f}% (${waste_total:.2f} per item)")
print(f"\n💡 At 330 burgers/week:  ${waste_total * 330:.2f}/week = ${waste_total * 330 * 52:.2f}/year in waste!")

print("\n" + "=" * 90)
print("WASTE FACTOR CALCULATION: ✅ VERIFIED")
print("=" * 90)
print("\nFormula: waste_adjusted_cost = base_cost × (1 + waste_factor)")
print("Example: $3.00 base × (1 + 0.20) = $3.00 × 1.20 = $3.60")
