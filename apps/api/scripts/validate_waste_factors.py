"""Validate that waste factors are realistic and provide value"""
import requests
import json

# Login
login_response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "synthetic@example.com", "password": "test123"}
)

token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("=" * 80)
print("WASTE FACTOR VALIDATION")
print("=" * 80)

# Get confirmed recipes with full ingredient details
response = requests.get(
    "http://localhost:8000/api/recipes/menu-items/confirmed",
    headers=headers
)

if response.status_code == 200:
    result = response.json()

    print(f"\n✓ Found {result['total']} confirmed recipes\n")

    for item in result['items']:
        print(f"\n{'='*80}")
        print(f"{item['menu_item_name']} - ${item.get('menu_item_price', 'N/A')}")
        print(f"{'='*80}")

        # Check if waste factors exist
        has_waste_factors = any(float(ing.get('waste_factor', 0)) > 0 for ing in item['ingredients'])
        has_base_cost = any('base_cost' in ing for ing in item['ingredients'])

        if not has_waste_factors:
            print("❌ NO WASTE FACTORS - This is just showing estimated_cost")
            continue

        if not has_base_cost:
            print("❌ NO BASE_COST - Cannot calculate waste impact")
            continue

        print("✓ Has waste factors and base costs\n")

        # Calculate totals
        base_total = sum(float(ing.get('base_cost', ing['estimated_cost'])) for ing in item['ingredients'])
        waste_total = sum(
            float(ing.get('base_cost', ing['estimated_cost'])) * float(ing.get('waste_factor', 0))
            for ing in item['ingredients']
        )
        total_cost = sum(float(ing['estimated_cost']) for ing in item['ingredients'])

        print(f"Base Cost:  ${base_total:.2f}")
        print(f"Waste Cost: ${waste_total:.2f} ({(waste_total/base_total*100):.1f}%)")
        print(f"True COGS:  ${total_cost:.2f}")

        # Validate the math
        expected_total = base_total + waste_total
        if abs(expected_total - total_cost) > 0.01:
            print(f"\n⚠️  MATH ERROR: base + waste = ${expected_total:.2f} but total = ${total_cost:.2f}")
        else:
            print(f"✓ Math checks out: ${base_total:.2f} + ${waste_total:.2f} = ${total_cost:.2f}")

        # Calculate margin impact
        if item.get('menu_item_price'):
            price = float(item['menu_item_price'])
            margin_without_waste = ((price - base_total) / price * 100)
            margin_with_waste = ((price - total_cost) / price * 100)
            impact = margin_without_waste - margin_with_waste

            print(f"\n📊 MARGIN IMPACT:")
            print(f"   Without waste: {margin_without_waste:.1f}%")
            print(f"   With waste:    {margin_with_waste:.1f}%")
            print(f"   Impact:        -{impact:.1f}% (${waste_total:.2f} hidden cost)")

            # Is this significant?
            if impact < 1.0:
                print(f"   ⚠️  Impact is minimal (<1%) - may not be worth showing")
            elif impact > 10.0:
                print(f"   ⚠️  Impact seems unrealistically high (>10%) - check waste factors")
            else:
                print(f"   ✓ Impact is realistic (1-10% range)")

        # Check individual ingredient waste factors
        print(f"\n   Ingredient Waste Factors:")
        high_waste_count = 0
        for ing in item['ingredients']:
            waste_pct = float(ing.get('waste_factor', 0)) * 100
            base = float(ing.get('base_cost', ing['estimated_cost']))

            if waste_pct > 0:
                # Check if waste factor is realistic for ingredient type
                name = ing['name'].lower()

                # Define realistic ranges
                is_realistic = True
                reason = ""

                if 'lettuce' in name or 'greens' in name:
                    if waste_pct < 10 or waste_pct > 25:
                        is_realistic = False
                        reason = "(leafy greens typically 10-25%)"
                elif 'beef' in name or 'meat' in name:
                    if waste_pct < 10 or waste_pct > 30:
                        is_realistic = False
                        reason = "(meat typically 10-30%)"
                elif 'fish' in name:
                    if waste_pct < 15 or waste_pct > 40:
                        is_realistic = False
                        reason = "(fish typically 15-40%)"
                elif 'cheese' in name or 'dairy' in name:
                    if waste_pct > 10:
                        is_realistic = False
                        reason = "(dairy typically <10%)"
                elif 'oil' in name or 'salt' in name or 'spice' in name:
                    if waste_pct > 5:
                        is_realistic = False
                        reason = "(condiments typically <5%)"

                status = "✓" if is_realistic else "⚠️ "
                print(f"   {status} {ing['name']:<25} {waste_pct:>5.1f}% waste  ${base:.2f} → ${float(ing['estimated_cost']):.2f}  {reason}")

                if waste_pct >= 20:
                    high_waste_count += 1

        # Summary assessment
        print(f"\n   Assessment:")
        if high_waste_count > 0:
            print(f"   • {high_waste_count} high-waste ingredients (≥20%) - these drive the cost")

        # Check if this provides actionable insights
        if waste_total > 0.50 and impact > 2.0:
            print(f"   ✓ PROVIDES VALUE: ${waste_total:.2f} hidden cost = {impact:.1f}% margin impact")
            print(f"     → User can identify high-waste ingredients and optimize")
        elif waste_total < 0.20:
            print(f"   ⚠️  LOW VALUE: Only ${waste_total:.2f} waste - may not be worth highlighting")
        else:
            print(f"   ? MARGINAL VALUE: ${waste_total:.2f} waste - borderline useful")

else:
    print(f"Error: {response.text}")
