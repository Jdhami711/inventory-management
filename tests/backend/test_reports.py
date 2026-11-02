"""
Tests for the reports API endpoints (quarterly and monthly trends).
"""
import pytest


class TestReportsEndpoints:
    """Test suite for report endpoints, including the global filters."""

    def test_get_quarterly_reports(self, client):
        """Test the unfiltered quarterly report structure."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        for q in data:
            for field in ("quarter", "total_orders", "total_revenue",
                          "delivered_orders", "avg_order_value", "fulfillment_rate"):
                assert field in q
            assert 0 <= q["fulfillment_rate"] <= 100

        quarters = [q["quarter"] for q in data]
        assert quarters == sorted(quarters)

    def test_get_monthly_trends(self, client):
        """Test the unfiltered monthly trends structure."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for m in data:
            assert len(m["month"]) == 7
            assert m["order_count"] > 0
            assert m["revenue"] > 0

        months = [m["month"] for m in data]
        assert months == sorted(months)

    def test_unfiltered_totals_match_orders(self, client):
        """Test that report totals add up to the orders endpoint."""
        orders = client.get("/api/orders").json()
        monthly = client.get("/api/reports/monthly-trends").json()
        quarterly = client.get("/api/reports/quarterly").json()

        assert sum(m["order_count"] for m in monthly) == len(orders)
        assert sum(q["total_orders"] for q in quarterly) == len(orders)
        expected_revenue = sum(o["total_value"] for o in orders)
        assert abs(sum(m["revenue"] for m in monthly) - expected_revenue) < 0.01

    def test_all_values_behave_like_no_filter(self, client):
        """Test that 'all' (what the filter bar sends) is the same as no filter."""
        unfiltered = client.get("/api/reports/monthly-trends").json()
        with_all = client.get(
            "/api/reports/monthly-trends?warehouse=all&category=all&status=all&month=all"
        ).json()
        assert with_all == unfiltered

    @pytest.mark.parametrize("path", ["/api/reports/quarterly", "/api/reports/monthly-trends"])
    def test_warehouse_filter_matches_orders(self, client, path):
        """Test that filtering by warehouse reports the same order count as /api/orders."""
        expected = len(client.get("/api/orders?warehouse=Tokyo").json())
        assert expected > 0

        data = client.get(f"{path}?warehouse=Tokyo").json()
        key = "total_orders" if "quarterly" in path else "order_count"
        assert sum(item[key] for item in data) == expected

    def test_category_and_status_filters_match_orders(self, client):
        """Test that category and status filters narrow the report like the orders list."""
        query = "category=Sensors&status=Delivered"
        expected = client.get(f"/api/orders?{query}").json()

        monthly = client.get(f"/api/reports/monthly-trends?{query}").json()
        assert sum(m["order_count"] for m in monthly) == len(expected)
        assert abs(sum(m["revenue"] for m in monthly) - sum(o["total_value"] for o in expected)) < 0.01

        # Every remaining order is Delivered, so fulfillment must be 100%
        quarterly = client.get(f"/api/reports/quarterly?{query}").json()
        assert all(q["fulfillment_rate"] == 100 for q in quarterly)

    def test_single_month_filter(self, client):
        """Test that a month filter leaves only that month in the trends."""
        data = client.get("/api/reports/monthly-trends?month=2025-03").json()
        assert [m["month"] for m in data] == ["2025-03"]

        quarterly = client.get("/api/reports/quarterly?month=2025-03").json()
        assert [q["quarter"] for q in quarterly] == ["Q1-2025"]

    def test_quarter_filter(self, client):
        """Test that a quarter filter keeps only that quarter's months."""
        data = client.get("/api/reports/monthly-trends?month=Q2-2025").json()
        assert len(data) > 0
        assert all(m["month"] in ("2025-04", "2025-05", "2025-06") for m in data)

    def test_filters_with_no_matches_return_empty_list(self, client):
        """Test that a filter combination with no orders returns [] rather than an error."""
        for path in ("/api/reports/quarterly", "/api/reports/monthly-trends"):
            response = client.get(f"{path}?warehouse=Nowhere")
            assert response.status_code == 200
            assert response.json() == []

    def test_revenue_is_rounded_to_cents(self, client):
        """Test that summed revenue carries no floating point noise."""
        for m in client.get("/api/reports/monthly-trends").json():
            assert m["revenue"] == round(m["revenue"], 2)
        for q in client.get("/api/reports/quarterly").json():
            assert q["total_revenue"] == round(q["total_revenue"], 2)
