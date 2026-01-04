"""Test the recipe API endpoint"""
import requests
import json

# Login
login_response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "synthetic@example.com", "password": "test123"}
)
token = login_response.json()["access_token"]

# Get unconfirmed recipes
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8000/api/recipes/menu-items/unconfirmed",
    headers=headers
)

print("Status:", response.status_code)
print("\nResponse:")
print(json.dumps(response.json(), indent=2))
