"""
Tests for restocking API endpoints.
"""
import pytest

import mock_data


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """Reset submitted restock orders around every test.

    Orders live in a module-level list that main.py imported by name, so it must
    be emptied in place (.clear()). Rebinding mock_data.restock_orders would
    leave main.py pointing at the old list and the reset would silently do nothing.
    """
    mock_data.restock_orders.clear()
    yield
    mock_data.restock_orders.clear()


def _candidates(client):
    """Forecast items that should be restock candidates, ranked by demand gap."""
    forecasts = client.get("/api/demand").json()
    ranked = [
        f for f in forecasts
        if f["unit_cost"] is not None and f["forecasted_demand"] > f["current_demand"]
    ]
    return sorted(
        ranked,
        key=lambda f: (-(f["forecasted_demand"] - f["current_demand"]), f["item_sku"]),
    )


class TestRestockRecommendations:
    """Test suite for GET /api/restocking/recommendations."""

    def test_demand_forecasts_include_cost_and_lead_time(self, client):
        """Test that every forecast now carries a unit cost and lead time."""
        data = client.get("/api/demand").json()
        assert len(data) > 0
        for forecast in data:
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["lead_time_days"] > 0

    def test_recommendations_response_structure(self, client):
        """Test the shape of the recommendations response."""
        response = client.get("/api/restocking/recommendations?budget=1000")
        assert response.status_code == 200

        data = response.json()
        for field in ("budget", "total_cost", "remaining", "total_needed_cost", "items"):
            assert field in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

        item = data["items"][0]
        for field in ("sku", "name", "trend", "quantity", "unit_cost", "line_cost", "lead_time_days"):
            assert field in item
        assert isinstance(item["quantity"], int)

    def test_zero_budget_recommends_nothing(self, client):
        """Test that a zero budget buys nothing but still reports the full cost."""
        data = client.get("/api/restocking/recommendations?budget=0").json()
        assert data["items"] == []
        assert data["total_cost"] == 0
        assert data["remaining"] == 0
        assert data["total_needed_cost"] > 0

    def test_negative_budget_rejected(self, client):
        """Test that a negative budget is a 400."""
        response = client.get("/api/restocking/recommendations?budget=-1")
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()

    def test_missing_budget_rejected(self, client):
        """Test that budget is a required query parameter."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 422

    def test_total_cost_never_exceeds_budget(self, client):
        """Test the budget is respected at many budget levels."""
        for budget in (1, 10, 50, 99.99, 250, 500, 1000, 2500, 4000, 100000):
            data = client.get(f"/api/restocking/recommendations?budget={budget}").json()
            assert data["total_cost"] <= budget + 0.001
            assert abs(data["total_cost"] + data["remaining"] - budget) < 0.01

    def test_total_cost_matches_line_costs(self, client):
        """Test that total_cost is the sum of the recommended lines."""
        data = client.get("/api/restocking/recommendations?budget=1500").json()
        assert abs(sum(i["line_cost"] for i in data["items"]) - data["total_cost"]) < 0.01
        for item in data["items"]:
            assert abs(item["quantity"] * item["unit_cost"] - item["line_cost"]) < 0.01

    def test_quantity_equals_demand_gap(self, client):
        """Test that recommended quantity is forecast minus current demand."""
        gaps = {
            f["item_sku"]: f["forecasted_demand"] - f["current_demand"]
            for f in client.get("/api/demand").json()
        }
        data = client.get("/api/restocking/recommendations?budget=100000").json()
        for item in data["items"]:
            assert item["quantity"] == gaps[item["sku"]]

    def test_unlimited_budget_recommends_every_candidate(self, client):
        """Test that a large budget buys all candidates for the full needed cost."""
        data = client.get("/api/restocking/recommendations?budget=100000").json()
        expected = [c["item_sku"] for c in _candidates(client)]
        assert [i["sku"] for i in data["items"]] == expected
        assert abs(data["total_cost"] - data["total_needed_cost"]) < 0.01

    def test_items_ordered_by_demand_gap(self, client):
        """Test that, with budget to spare, the largest gap comes first."""
        data = client.get("/api/restocking/recommendations?budget=100000").json()
        quantities = [i["quantity"] for i in data["items"]]
        assert quantities == sorted(quantities, reverse=True)

    def test_decreasing_demand_item_never_recommended(self, client):
        """Test that an item whose demand is falling is never a candidate."""
        for budget in (0, 500, 4000, 100000):
            data = client.get(f"/api/restocking/recommendations?budget={budget}").json()
            assert "MTR-304" not in [i["sku"] for i in data["items"]]

    def test_item_that_does_not_fit_is_skipped_not_split(self, client):
        """Test the greedy fill skips an unaffordable item and keeps going.

        Budget 500 cannot afford the top-ranked lines (their full quantity costs
        more), but the small stable-demand items later in the ranking still fit.
        No item is ever bought in a partial quantity.
        """
        candidates = _candidates(client)
        top = candidates[0]
        top_cost = (top["forecasted_demand"] - top["current_demand"]) * top["unit_cost"]
        assert top_cost > 500  # precondition for this scenario

        data = client.get("/api/restocking/recommendations?budget=500").json()
        skus = [i["sku"] for i in data["items"]]
        assert top["item_sku"] not in skus
        assert len(data["items"]) > 0
        gaps = {c["item_sku"]: c["forecasted_demand"] - c["current_demand"] for c in candidates}
        for item in data["items"]:
            assert item["quantity"] == gaps[item["sku"]]

    def test_larger_budget_never_buys_less(self, client):
        """Test that raising the budget never lowers planned spend."""
        previous = -1
        for budget in range(0, 4500, 250):
            total = client.get(f"/api/restocking/recommendations?budget={budget}").json()["total_cost"]
            assert total >= previous
            previous = total


class TestRestockOrders:
    """Test suite for POST and GET /api/restocking/orders."""

    def test_create_order_happy_path(self, client):
        """Test submitting a small order."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"sku": "FLT-405", "quantity": 10}]},
        )
        assert response.status_code == 201

        order = response.json()
        assert order["order_number"] == "RST-0001"
        assert order["status"] == "Submitted"
        assert order["total_value"] == 64.0
        assert order["items"][0]["sku"] == "FLT-405"
        assert order["items"][0]["name"] == "Oil Filter Cartridge"
        assert order["items"][0]["unit_cost"] == 6.4
        assert order["items"][0]["line_cost"] == 64.0

    def test_small_order_lead_time_is_slowest_item(self, client):
        """Test lead time is the slowest item's lead time when the order is small."""
        order = client.post(
            "/api/restocking/orders",
            json={"items": [
                {"sku": "FLT-405", "quantity": 1},   # 5 days
                {"sku": "BRG-102", "quantity": 1},   # 10 days
            ]},
        ).json()
        assert order["total_value"] < 2000
        assert order["lead_time_days"] == 10

    def test_large_order_adds_handling_days(self, client):
        """Test orders over the threshold take 2 extra days."""
        order = client.post(
            "/api/restocking/orders",
            json={"items": [
                {"sku": "WDG-001", "quantity": 150},  # 1875.00, 7 days
                {"sku": "GSK-203", "quantity": 100},  # 875.00, 5 days
                {"sku": "FLT-405", "quantity": 150},  # 960.00, 5 days
            ]},
        ).json()
        assert order["total_value"] == 3710.0
        assert order["lead_time_days"] == 9  # max 7 + 2 handling

    def test_expected_delivery_is_order_date_plus_lead_time(self, client):
        """Test the delivery date lines up with the reported lead time."""
        from datetime import date, timedelta

        order = client.post(
            "/api/restocking/orders",
            json={"items": [{"sku": "BRG-102", "quantity": 2}]},
        ).json()
        order_date = date.fromisoformat(order["order_date"])
        assert date.fromisoformat(order["expected_delivery"]) == order_date + timedelta(days=order["lead_time_days"])

    def test_client_supplied_prices_are_ignored(self, client):
        """Test the server prices the order from its own data."""
        order = client.post(
            "/api/restocking/orders",
            json={"items": [{"sku": "FLT-405", "quantity": 10, "unit_cost": 0.01, "line_cost": 0.1}]},
        ).json()
        assert order["total_value"] == 64.0
        assert order["items"][0]["unit_cost"] == 6.4

    def test_order_numbers_increment(self, client):
        """Test sequential order numbers."""
        numbers = [
            client.post("/api/restocking/orders", json={"items": [{"sku": "FLT-405", "quantity": 1}]}).json()["order_number"]
            for _ in range(3)
        ]
        assert numbers == ["RST-0001", "RST-0002", "RST-0003"]

    def test_reject_empty_order(self, client):
        """Test an order with no items is a 400."""
        response = client.post("/api/restocking/orders", json={"items": []})
        assert response.status_code == 400

    def test_reject_zero_and_negative_quantity(self, client):
        """Test non-positive quantities are a 400."""
        for quantity in (0, -5):
            response = client.post(
                "/api/restocking/orders",
                json={"items": [{"sku": "WDG-001", "quantity": quantity}]},
            )
            assert response.status_code == 400

    def test_reject_unknown_sku(self, client):
        """Test an unknown SKU is a 400 and nothing is stored."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"sku": "NOPE-000", "quantity": 1}]},
        )
        assert response.status_code == 400
        assert "cannot be ordered" in response.json()["detail"]
        assert client.get("/api/restocking/orders").json() == []

    def test_reject_duplicate_sku(self, client):
        """Test the same SKU twice in one order is a 400."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"sku": "WDG-001", "quantity": 1}, {"sku": "WDG-001", "quantity": 2}]},
        )
        assert response.status_code == 400

    def test_reject_malformed_body(self, client):
        """Test a body missing required fields fails validation."""
        response = client.post("/api/restocking/orders", json={"items": [{"sku": "WDG-001"}]})
        assert response.status_code == 422

    def test_invalid_order_does_not_consume_order_number(self, client):
        """Test a rejected order leaves numbering untouched."""
        client.post("/api/restocking/orders", json={"items": []})
        order = client.post(
            "/api/restocking/orders", json={"items": [{"sku": "FLT-405", "quantity": 1}]}
        ).json()
        assert order["order_number"] == "RST-0001"

    def test_list_orders_empty(self, client):
        """Test listing orders before any are submitted."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_orders_newest_first(self, client):
        """Test submitted orders come back newest first."""
        for sku in ("FLT-405", "WDG-001", "GSK-203"):
            client.post("/api/restocking/orders", json={"items": [{"sku": sku, "quantity": 1}]})

        numbers = [o["order_number"] for o in client.get("/api/restocking/orders").json()]
        assert numbers == ["RST-0003", "RST-0002", "RST-0001"]

    def test_recommendation_can_be_submitted_as_order(self, client):
        """Test the recommended lines convert into an order with the same total."""
        rec = client.get("/api/restocking/recommendations?budget=1500").json()
        assert len(rec["items"]) > 0

        order = client.post(
            "/api/restocking/orders",
            json={"items": [{"sku": i["sku"], "quantity": i["quantity"]} for i in rec["items"]]},
        ).json()
        assert abs(order["total_value"] - rec["total_cost"]) < 0.01
        assert order["total_value"] <= 1500

    def test_submitted_orders_do_not_affect_existing_orders_or_dashboard(self, client):
        """Test restock orders stay out of the main orders list and dashboard totals."""
        orders_before = client.get("/api/orders").json()
        summary_before = client.get("/api/dashboard/summary").json()
        quarterly_before = client.get("/api/reports/quarterly").json()

        client.post(
            "/api/restocking/orders",
            json={"items": [{"sku": "WDG-001", "quantity": 150}]},
        )

        assert client.get("/api/orders").json() == orders_before
        assert client.get("/api/dashboard/summary").json() == summary_before
        assert client.get("/api/reports/quarterly").json() == quarterly_before
