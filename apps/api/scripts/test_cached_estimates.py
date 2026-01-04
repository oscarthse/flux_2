"""Test the cached recipe estimates endpoint"""
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

# Get recipe estimates
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8000/api/recipes/menu-items/estimates",
    headers=headers
)

print("Status:", response.status_code)
print("\nResponse:")
if response.status_code == 200:
    print(json.dumps(response.json(), indent=2, default=str))
else:
    print(response.text)
