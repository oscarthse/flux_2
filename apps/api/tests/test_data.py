"""
Tests for data upload endpoints.
"""
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.user import User
from src.models.restaurant import Restaurant
from src.models.data_upload import DataUpload
from src.models.transaction import Transaction, TransactionItem


class TestUpload:
    """Tests for POST /api/data/upload."""

    def test_upload_csv_success(
        self,
        client: TestClient,
        auth_headers_with_restaurant: dict,
        db: Session
    ):
        """Test successful CSV upload."""
        csv_content = """date,menu_item,quantity,unit_price,total
2024-01-15,Paella,2,18.50,37.00
2024-01-15,Sangria,4,6.00,24.00
2024-01-16,Tapas,3,12.00,36.00"""

        files = {"file": ("test_data.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            "/api/data/upload",
            headers=auth_headers_with_restaurant,
            files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert "3 rows" in data["message"]
        assert "3 inserted" in data["message"]

    def test_upload_csv_partial_failure(
        self,
        client: TestClient,
        auth_headers_with_restaurant: dict
    ):
        """Test CSV upload with some invalid rows."""
        csv_content = """date,menu_item,quantity,unit_price,total
2024-01-15,Paella,2,18.50,37.00
invalid-date,Sangria,4,6.00,24.00
2024-01-16,Tapas,-1,12.00,36.00"""

        files = {"file": ("test_data.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post(
            "/api/data/upload",
            headers=auth_headers_with_restaurant,
            files=files
        )

        assert response.status_code == 200
        data = response.json()
        # At least one row should have failed
        assert "failed" in data["message"]

    def test_upload_non_csv_rejected(
        self,
        client: TestClient,
        auth_headers_with_restaurant: dict
    ):
        """Test that non-CSV files are rejected."""
        files = {"file": ("test.txt", io.BytesIO(b"some text content"), "text/plain")}
        response = client.post(
            "/api/data/upload",
            headers=auth_headers_with_restaurant,
            files=files
        )

        assert response.status_code == 400
        assert "csv" in response.json()["detail"].lower()

    def test_upload_requires_restaurant(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test that upload requires user to have a restaurant."""
        csv_content = "date,menu_item,quantity,unit_price,total\n2024-01-15,Paella,2,18.50,37.00"
        files = {"file": ("test_data.csv", io.BytesIO(csv_content.encode()), "text/csv")}

        response = client.post(
            "/api/data/upload",
            headers=auth_headers,
            files=files
        )

        assert response.status_code == 400
        assert "restaurant" in response.json()["detail"].lower()

    def test_upload_requires_auth(self, client: TestClient):
        """Test that upload requires authentication."""
        csv_content = "date,menu_item,quantity,unit_price,total\n2024-01-15,Paella,2,18.50,37.00"
        files = {"file": ("test_data.csv", io.BytesIO(csv_content.encode()), "text/csv")}

        response = client.post("/api/data/upload", files=files)

        assert response.status_code == 401


class TestListUploads:
    """Tests for GET /api/data/uploads."""

    def test_list_uploads_empty(
        self,
        client: TestClient,
        auth_headers_with_restaurant: dict
    ):
        """Test listing uploads when none exist."""
        response = client.get(
            "/api/data/uploads",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 200
        data = response.json()
        assert "uploads" in data
        assert isinstance(data["uploads"], list)

    def test_list_uploads_after_upload(
        self,
        client: TestClient,
        auth_headers_with_restaurant: dict
    ):
        """Test listing uploads after creating one."""
        # First upload a file
        csv_content = "date,menu_item,quantity,unit_price,total\n2024-01-15,Paella,2,18.50,37.00"
        files = {"file": ("test_data.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        client.post(
            "/api/data/upload",
            headers=auth_headers_with_restaurant,
            files=files
        )

        # Then list uploads
        response = client.get(
            "/api/data/uploads",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["uploads"]) >= 1

    def test_list_uploads_requires_auth(self, client: TestClient):
        """Test that listing uploads requires authentication."""
        response = client.get("/api/data/uploads")

        assert response.status_code == 401


class TestGetUploadStatus:
    """Tests for GET /api/data/uploads/{id}."""

    def test_get_upload_status(
        self,
        client: TestClient,
        auth_headers_with_restaurant: dict
    ):
        """Test getting status of a specific upload."""
        # First upload a file
        csv_content = "date,menu_item,quantity,unit_price,total\n2024-01-15,Paella,2,18.50,37.00"
        files = {"file": ("test_data.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        upload_response = client.post(
            "/api/data/upload",
            headers=auth_headers_with_restaurant,
            files=files
        )
        upload_id = upload_response.json()["upload_id"]

        # Get status
        response = client.get(
            f"/api/data/uploads/{upload_id}",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == upload_id
        assert "status" in data

    def test_get_nonexistent_upload(
        self,
        client: TestClient,
        auth_headers_with_restaurant: dict
    ):
        """Test getting status of nonexistent upload."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(
            f"/api/data/uploads/{fake_id}",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 404
