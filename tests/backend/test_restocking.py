"""
Tests for the restocking order creation endpoint (POST /api/orders).
"""
import pytest


class TestCreateOrderEndpoint:
    """Test suite for creating restocking orders."""

    def _payload(self):
        """A valid two-item restocking payload."""
        return {
            "items": [
                {"sku": "SRV-301", "name": "Micro Servo Motor",
                 "quantity": 150, "unit_price": 445.0},
                {"sku": "STP-304", "name": "Stepper Motor NEMA 23",
                 "quantity": 100, "unit_price": 285.0},
            ],
            "warehouse": "A",
        }

    def test_create_order_success(self, client):
        """Test creating a restocking order returns the created order."""
        response = client.post("/api/orders", json=self._payload())
        assert response.status_code == 200

        order = response.json()
        # Server-assigned fields
        assert "id" in order
        assert order["order_number"].startswith("ORD-2025-")
        assert order["status"] == "Submitted"
        assert order["customer"] == "Internal Restock"
        assert order["warehouse"] == "A"
        # Category is derived from the first item's inventory record
        assert order["category"] == "Actuators"
        assert len(order["items"]) == 2

    def test_create_order_total_value_calculation(self, client):
        """Test total_value equals the sum of quantity * unit_price."""
        payload = self._payload()
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 200

        order = response.json()
        expected_total = sum(i["quantity"] * i["unit_price"] for i in payload["items"])
        assert abs(order["total_value"] - expected_total) < 0.01
        assert order["total_value"] == 95250.0

    def test_create_order_lead_time_is_14_days(self, client):
        """Test expected_delivery is a fixed 14 days after order_date."""
        from datetime import datetime

        response = client.post("/api/orders", json=self._payload())
        assert response.status_code == 200

        order = response.json()
        order_date = datetime.fromisoformat(order["order_date"])
        expected_delivery = datetime.fromisoformat(order["expected_delivery"])
        assert (expected_delivery - order_date).days == 14
        # ISO datetime with a time component, like existing orders
        assert "T" in order["order_date"]
        assert "T" in order["expected_delivery"]

    def test_created_order_appears_in_orders_list(self, client):
        """Test a submitted order is retrievable via GET /api/orders."""
        create_response = client.post("/api/orders", json=self._payload())
        assert create_response.status_code == 200
        created = create_response.json()

        list_response = client.get("/api/orders")
        assert list_response.status_code == 200
        orders = list_response.json()

        match = next((o for o in orders if o["id"] == created["id"]), None)
        assert match is not None
        assert match["status"] == "Submitted"
        assert match["order_number"] == created["order_number"]

    def test_created_order_retrievable_by_id(self, client):
        """Test a submitted order is retrievable via GET /api/orders/{id}."""
        created = client.post("/api/orders", json=self._payload()).json()

        response = client.get(f"/api/orders/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_create_order_defaults_customer(self, client):
        """Test the customer defaults to 'Internal Restock' when omitted."""
        payload = {
            "items": [
                {"sku": "PSU-501", "name": "5V 10A Switching Power Supply",
                 "quantity": 50, "unit_price": 18.99},
            ]
        }
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 200
        assert response.json()["customer"] == "Internal Restock"

    def test_create_order_empty_items_rejected(self, client):
        """Test posting an order with no items returns 400."""
        response = client.post("/api/orders", json={"items": []})
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_create_order_missing_items_field(self, client):
        """Test posting without the required items field returns 422."""
        response = client.post("/api/orders", json={"warehouse": "A"})
        assert response.status_code == 422

    def test_create_order_item_structure(self, client):
        """Test the returned items preserve the submitted structure."""
        response = client.post("/api/orders", json=self._payload())
        order = response.json()

        for item in order["items"]:
            assert "sku" in item
            assert "name" in item
            assert isinstance(item["quantity"], int)
            assert isinstance(item["unit_price"], (int, float))
