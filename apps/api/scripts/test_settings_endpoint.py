"""Test settings endpoint"""
import requests

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
print("SETTINGS ENDPOINT TEST")
print("=" * 80)

# Get feature settings
print("\n1. GET /api/settings/features")
response = requests.get(
    "http://localhost:8000/api/settings/features",
    headers=headers
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

# Update feature settings
print("\n2. PUT /api/settings/features (disable waste factors)")
response = requests.put(
    "http://localhost:8000/api/settings/features",
    headers=headers,
    json={"waste_factors_enabled": False}
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

# Get again to verify
print("\n3. GET /api/settings/features (verify update)")
response = requests.get(
    "http://localhost:8000/api/settings/features",
    headers=headers
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

# Re-enable
print("\n4. PUT /api/settings/features (re-enable waste factors)")
response = requests.put(
    "http://localhost:8000/api/settings/features",
    headers=headers,
    json={"waste_factors_enabled": True}
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
