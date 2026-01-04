"""
Tests for health check endpoint.
"""
from fastapi.testclient import TestClient


class TestHealth:
    """Tests for health check endpoints."""

    def test_basic_health(self, client: TestClient):
        """Test basic health check."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_api_health_with_services(self, client: TestClient):
        """Test API health check with service status."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "services" in data
        assert "database" in data["services"]
