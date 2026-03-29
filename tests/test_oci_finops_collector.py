"""
Testes para OCIFinOpsCollector: regras de recomendação e agregação de dados.
"""

import pytest
from types import SimpleNamespace


def _fake_item(
    service="Compute",
    computed_amount=100.0,
    currency="BRL",
    compartment_name="root",
    sku_name="Oracle OCPU - Standard - E4",
    unit="OCPU_HOURS",
    computed_quantity=10.0,
):
    return SimpleNamespace(
        service=service,
        computed_amount=computed_amount,
        currency=currency,
        compartment_name=compartment_name,
        sku_name=sku_name,
        unit=unit,
        computed_quantity=computed_quantity,
    )


# ---------------------------------------------------------------------------
# _aggregate_items_by_key
# ---------------------------------------------------------------------------

class TestAggregateItemsByKey:
    def _collector(self):
        from collectors.oci_finops_collector import OCIFinOpsCollector
        return OCIFinOpsCollector

    def test_sum_by_service(self):
        cls = self._collector()
        items = [
            _fake_item(service="Compute", computed_amount=50.0),
            _fake_item(service="Compute", computed_amount=30.0),
            _fake_item(service="Storage", computed_amount=20.0),
        ]
        result = cls._aggregate_items_by_key(items, "service")
        assert result["Compute"] == pytest.approx(80.0)
        assert result["Storage"] == pytest.approx(20.0)

    def test_sum_by_compartment(self):
        cls = self._collector()
        items = [
            _fake_item(compartment_name="prod", computed_amount=200.0),
            _fake_item(compartment_name="dev", computed_amount=50.0),
            _fake_item(compartment_name="prod", computed_amount=100.0),
        ]
        result = cls._aggregate_items_by_key(items, "compartment_name")
        assert result["prod"] == pytest.approx(300.0)
        assert result["dev"] == pytest.approx(50.0)

    def test_skips_none_amount(self):
        cls = self._collector()
        items = [
            _fake_item(service="Compute", computed_amount=None),
            _fake_item(service="Compute", computed_amount=50.0),
        ]
        result = cls._aggregate_items_by_key(items, "service")
        assert result["Compute"] == pytest.approx(50.0)

    def test_skips_zero_amount(self):
        cls = self._collector()
        items = [
            _fake_item(service="Compute", computed_amount=0.0),
            _fake_item(service="Storage", computed_amount=0.0005),
        ]
        result = cls._aggregate_items_by_key(items, "service")
        assert "Compute" not in result
        assert "Storage" not in result

    def test_empty_items(self):
        cls = self._collector()
        result = cls._aggregate_items_by_key([], "service")
        assert result == {}


# ---------------------------------------------------------------------------
# _parse_shape_family
# ---------------------------------------------------------------------------

class TestParseShapeFamily:
    def _fn(self):
        from collectors.oci_finops_collector import OCIFinOpsCollector
        return OCIFinOpsCollector._parse_shape_family

    def test_windows_licensing(self):
        fn = self._fn()
        assert fn("Windows OCPU - Compute") == "Windows OS Licensing"
        assert fn("Oracle Windows Licensing - VM") == "Windows OS Licensing"

    def test_oracle_ocpu_pattern(self):
        fn = self._fn()
        assert fn("Oracle OCPU - Standard3 - E4") == "Standard3"
        assert fn("Oracle OCPU - DenseIO - D2") == "DenseIO"
        assert fn("Oracle OCPU - Optimized3 - X9") == "Optimized3"

    def test_gpu_pattern(self):
        fn = self._fn()
        assert fn("Oracle GPU2 Instance") == "GPU2"
        assert fn("Oracle GPU3.20 Compute") == "GPU3"

    def test_default_other(self):
        fn = self._fn()
        assert fn("Some Unknown SKU Name") == "Other"
        assert fn("") == "Other"

    def test_case_insensitive_windows(self):
        fn = self._fn()
        assert fn("WINDOWS SERVER LICENSE") == "Windows OS Licensing"


# ---------------------------------------------------------------------------
# _build_recommendations
# ---------------------------------------------------------------------------

class TestBuildRecommendations:
    def _fn(self):
        from collectors.oci_finops_collector import OCIFinOpsCollector
        return OCIFinOpsCollector._build_recommendations

    def _empty_inputs(self):
        by_compartment = []
        by_service = []
        compute_shapes = []
        total_cost = 1000.0
        return by_compartment, by_service, compute_shapes, total_cost

    # Rule 1: Windows licensing > 10% of total
    def test_rule_windows_over_10pct(self):
        fn = self._fn()
        compute_shapes = [
            {"shape_family": "Windows OS Licensing", "cost": 150.0, "ocpu_hours": 100, "est_ocpus": 1},
            {"shape_family": "Standard3", "cost": 850.0, "ocpu_hours": 800, "est_ocpus": 8},
        ]
        recs = fn([], [], compute_shapes, total_cost=1000.0)
        titles = [r["title"] for r in recs]
        assert any("Windows" in t for t in titles)
        win_rec = next(r for r in recs if "Windows" in r["title"])
        assert win_rec["severity"] == "warning"
        assert win_rec["potential_savings_brl"] > 0

    def test_rule_windows_under_threshold(self):
        fn = self._fn()
        compute_shapes = [
            {"shape_family": "Windows OS Licensing", "cost": 50.0, "ocpu_hours": 50, "est_ocpus": 1},
            {"shape_family": "Standard3", "cost": 950.0, "ocpu_hours": 900, "est_ocpus": 9},
        ]
        recs = fn([], [], compute_shapes, total_cost=1000.0)
        assert not any("Windows" in r["title"] for r in recs)

    # Rule 2: OKE Enhanced clusters detected
    def test_rule_oke_enhanced_detected(self):
        fn = self._fn()
        by_service = [
            {"service": "OKE Enhanced", "cost": 200.0, "currency": "BRL", "prev_cost": 180.0, "variation_pct": 11.0},
        ]
        recs = fn([], by_service, [], total_cost=1000.0)
        assert any("OKE" in r["title"] for r in recs)
        oke_rec = next(r for r in recs if "OKE" in r["title"])
        assert oke_rec["severity"] == "info"

    def test_rule_oke_not_present(self):
        fn = self._fn()
        by_service = [
            {"service": "Compute", "cost": 500.0, "currency": "BRL", "prev_cost": 480.0, "variation_pct": 4.0},
        ]
        recs = fn([], by_service, [], total_cost=1000.0)
        assert not any("OKE" in r["title"] for r in recs)

    # Rule 3: Single compartment > 60% of total
    def test_rule_compartment_concentration(self):
        fn = self._fn()
        by_compartment = [
            {"compartment": "prod", "cost": 700.0, "pct": 70.0},
            {"compartment": "dev", "cost": 300.0, "pct": 30.0},
        ]
        recs = fn(by_compartment, [], [], total_cost=1000.0)
        titles_lower = [r["title"].lower() for r in recs]
        assert any("concentra" in t for t in titles_lower)
        conc_rec = next(r for r in recs if "concentra" in r["title"].lower())
        assert conc_rec["severity"] == "info"

    def test_rule_compartment_no_concentration(self):
        fn = self._fn()
        by_compartment = [
            {"compartment": "prod", "cost": 550.0, "pct": 55.0},
            {"compartment": "dev", "cost": 450.0, "pct": 45.0},
        ]
        recs = fn(by_compartment, [], [], total_cost=1000.0)
        assert not any("concentra" in r["title"].lower() for r in recs)

    # Rule 4: Service variation > 30% AND prev_cost > 100
    def test_rule_service_variation_anomaly(self):
        fn = self._fn()
        by_service = [
            {"service": "Database", "cost": 400.0, "currency": "BRL", "prev_cost": 200.0, "variation_pct": 100.0},
        ]
        recs = fn([], by_service, [], total_cost=1000.0)
        titles_lower = [r["title"].lower() for r in recs]
        assert any("anomalia" in t or "database" in t for t in titles_lower)
        anom_rec = next(r for r in recs if "anomalia" in r["title"].lower() or "database" in r["title"].lower())
        assert anom_rec["severity"] == "warning"

    def test_rule_variation_low_prev_cost_ignored(self):
        fn = self._fn()
        by_service = [
            {"service": "Database", "cost": 90.0, "currency": "BRL", "prev_cost": 50.0, "variation_pct": 80.0},
        ]
        recs = fn([], by_service, [], total_cost=1000.0)
        # prev_cost=50 <= 100 → rule must NOT fire
        assert not any("anomalia" in r["title"].lower() for r in recs)

    def test_rule_variation_under_threshold(self):
        fn = self._fn()
        by_service = [
            {"service": "Database", "cost": 250.0, "currency": "BRL", "prev_cost": 200.0, "variation_pct": 25.0},
        ]
        recs = fn([], by_service, [], total_cost=1000.0)
        assert not any("anomalia" in r["title"].lower() for r in recs)

    # Rule 5: MySQL storage > 40% of MySQL total
    def test_rule_mysql_storage_high(self):
        fn = self._fn()
        by_service = [
            {"service": "MySQL Database - Storage", "cost": 500.0, "currency": "BRL", "prev_cost": 480.0, "variation_pct": 4.0},
            {"service": "MySQL Database - Compute", "cost": 300.0, "currency": "BRL", "prev_cost": 290.0, "variation_pct": 3.0},
        ]
        recs = fn([], by_service, [], total_cost=1000.0)
        mysql_recs = [r for r in recs if "MySQL" in r["title"]]
        assert len(mysql_recs) > 0
        storage_rec = next((r for r in mysql_recs if "storage" in r["detail"].lower()), None)
        assert storage_rec is not None
        assert storage_rec["severity"] == "info"

    def test_rule_mysql_storage_low(self):
        fn = self._fn()
        by_service = [
            {"service": "MySQL Database - Storage", "cost": 100.0, "currency": "BRL", "prev_cost": 90.0, "variation_pct": 11.0},
            {"service": "MySQL Database - Compute", "cost": 700.0, "currency": "BRL", "prev_cost": 680.0, "variation_pct": 3.0},
        ]
        recs = fn([], by_service, [], total_cost=1000.0)
        mysql_storage_recs = [r for r in recs if "MySQL" in r["title"] and "storage" in r["detail"].lower()]
        assert len(mysql_storage_recs) == 0

    # Multiple rules firing together
    def test_multiple_rules_fire_together(self):
        fn = self._fn()
        by_compartment = [
            {"compartment": "prod", "cost": 750.0, "pct": 75.0},
        ]
        by_service = [
            {"service": "OKE Enhanced", "cost": 200.0, "currency": "BRL", "prev_cost": 180.0, "variation_pct": 11.0},
            {"service": "Database", "cost": 400.0, "currency": "BRL", "prev_cost": 150.0, "variation_pct": 166.0},
        ]
        compute_shapes = [
            {"shape_family": "Windows OS Licensing", "cost": 200.0, "ocpu_hours": 200, "est_ocpus": 2},
        ]
        recs = fn(by_compartment, by_service, compute_shapes, total_cost=1000.0)
        titles = [r["title"] for r in recs]
        titles_lower = [t.lower() for t in titles]
        assert any("Windows" in t for t in titles)
        assert any("OKE" in t for t in titles)
        assert any("concentra" in t for t in titles_lower)
        assert any("anomalia" in t or "database" in t.lower() for t in titles_lower)

    # Edge: zero / None values produce no recommendations for empty inputs
    def test_no_recommendations_for_empty_inputs(self):
        fn = self._fn()
        recs = fn([], [], [], total_cost=0.0)
        assert isinstance(recs, list)

    def test_recommendation_structure(self):
        fn = self._fn()
        compute_shapes = [
            {"shape_family": "Windows OS Licensing", "cost": 200.0, "ocpu_hours": 200, "est_ocpus": 2},
        ]
        recs = fn([], [], compute_shapes, total_cost=1000.0)
        assert len(recs) >= 1
        for rec in recs:
            assert "severity" in rec
            assert "title" in rec
            assert "detail" in rec
            assert "potential_savings_brl" in rec
            assert rec["severity"] in ("warning", "info", "critical")
