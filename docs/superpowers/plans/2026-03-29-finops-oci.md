# FinOps OCI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FinOps sub-tab to the Cloud tab showing OCI cost breakdown by compartment, service, compute shape, and automated recommendations.

**Architecture:** New `OCIFinOpsCollector` queries OCI Usage API with `group_by` dimensions to build cost breakdowns and generates rule-based recommendations. Backend integrates into `main.py` after existing OCI collection. Frontend adds a "FinOps OCI" sub-tab to `CloudTab` with KPI cards, DataTables, and recommendation cards.

**Tech Stack:** Python (oci SDK, tenacity), React (TypeScript, framer-motion, lucide-react, Tailwind CSS), Vite

---

## File Structure

### Backend (`/opt/weekly-report/`)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `collectors/oci_finops_collector.py` | Query OCI Usage API with group_by for compartment/service/shape breakdowns, generate recommendations |
| Create | `tests/test_oci_finops_collector.py` | Unit tests for collector logic (recommendation rules, data aggregation) |
| Modify | `main.py:203-214` | Call FinOps collector after existing OCI collection |
| Modify | `report/generator.py:64-76` | Pass `finops_data` through to `report_data` |

### Frontend (`/home/ubuntu/weekly-report-hub/`)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/types/report.ts` | Add FinOps type interfaces and `finops?` field to `ReportData` |
| Create | `src/components/dashboard/FinOpsTab.tsx` | FinOps sub-tab content: KPI cards, DataTables, recommendation cards |
| Modify | `src/components/dashboard/CloudTab.tsx:14-18` | Add "FinOps OCI" sub-tab, render `FinOpsTab` component |

---

## Task 1: OCI FinOps Collector — Tests

**Files:**
- Create: `tests/test_oci_finops_collector.py`

- [ ] **Step 1: Write tests for recommendation rules and data aggregation**

Create `tests/test_oci_finops_collector.py`:

```python
"""Tests for OCI FinOps collector — recommendation rules and aggregation."""

from collectors.oci_finops_collector import OCIFinOpsCollector


class TestBuildRecommendations:
    """Test recommendation rule engine against known data patterns."""

    def test_windows_licensing_above_10pct(self):
        shapes = [
            {"shape_family": "Standard - X9", "ocpu_hours": 27552, "est_ocpus": 40, "cost": 7263.0},
            {"shape_family": "Windows OS Licensing", "ocpu_hours": 12096, "est_ocpus": 18, "cost": 6133.0},
        ]
        by_service = [
            {"service": "Compute", "cost": 20057.0, "currency": "BRL", "prev_cost": 17200.0, "variation_pct": 16.6},
        ]
        by_compartment = [
            {"compartment": "Application", "cost": 20000.0, "pct": 65.0},
            {"compartment": "Database", "cost": 10000.0, "pct": 35.0},
        ]
        total = 30000.0

        recs = OCIFinOpsCollector._build_recommendations(by_compartment, by_service, shapes, total)

        windows_recs = [r for r in recs if "Windows" in r["title"]]
        assert len(windows_recs) == 1
        assert windows_recs[0]["severity"] == "warning"
        assert windows_recs[0]["potential_savings_brl"] == 6133.0

    def test_windows_licensing_below_10pct_no_rec(self):
        shapes = [
            {"shape_family": "Standard - X9", "ocpu_hours": 27552, "est_ocpus": 40, "cost": 7263.0},
            {"shape_family": "Windows OS Licensing", "ocpu_hours": 100, "est_ocpus": 1, "cost": 50.0},
        ]
        total = 30000.0

        recs = OCIFinOpsCollector._build_recommendations([], [], shapes, total)

        windows_recs = [r for r in recs if "Windows" in r["title"]]
        assert len(windows_recs) == 0

    def test_single_compartment_above_60pct(self):
        by_compartment = [
            {"compartment": "Application", "cost": 25000.0, "pct": 83.3},
            {"compartment": "Database", "cost": 5000.0, "pct": 16.7},
        ]

        recs = OCIFinOpsCollector._build_recommendations(by_compartment, [], [], 30000.0)

        concentration_recs = [r for r in recs if "concentra" in r["title"].lower()]
        assert len(concentration_recs) == 1
        assert concentration_recs[0]["severity"] == "info"

    def test_no_compartment_above_60pct(self):
        by_compartment = [
            {"compartment": "Application", "cost": 15000.0, "pct": 50.0},
            {"compartment": "Database", "cost": 15000.0, "pct": 50.0},
        ]

        recs = OCIFinOpsCollector._build_recommendations(by_compartment, [], [], 30000.0)

        concentration_recs = [r for r in recs if "concentra" in r["title"].lower()]
        assert len(concentration_recs) == 0

    def test_service_variation_above_30pct(self):
        by_service = [
            {"service": "Compute", "cost": 20000.0, "currency": "BRL", "prev_cost": 14000.0, "variation_pct": 42.8},
            {"service": "MySQL Database", "cost": 5000.0, "currency": "BRL", "prev_cost": 4800.0, "variation_pct": 4.2},
        ]

        recs = OCIFinOpsCollector._build_recommendations([], by_service, [], 25000.0)

        anomaly_recs = [r for r in recs if "anomalia" in r["title"].lower() or "Compute" in r["title"]]
        assert len(anomaly_recs) == 1
        assert anomaly_recs[0]["severity"] == "warning"

    def test_no_service_variation_above_30pct(self):
        by_service = [
            {"service": "Compute", "cost": 20000.0, "currency": "BRL", "prev_cost": 18000.0, "variation_pct": 11.1},
        ]

        recs = OCIFinOpsCollector._build_recommendations([], by_service, [], 20000.0)

        anomaly_recs = [r for r in recs if "anomalia" in r["title"].lower()]
        assert len(anomaly_recs) == 0

    def test_oke_enhanced_detected(self):
        by_service = [
            {"service": "Oracle Container Engine for Kubernetes - Enhanced Clusters", "cost": 3000.0, "currency": "BRL", "prev_cost": 2800.0, "variation_pct": 7.1},
        ]

        recs = OCIFinOpsCollector._build_recommendations([], by_service, [], 30000.0)

        oke_recs = [r for r in recs if "OKE" in r["title"]]
        assert len(oke_recs) == 1
        assert oke_recs[0]["severity"] == "info"

    def test_mysql_storage_above_40pct(self):
        by_service = [
            {"service": "MySQL Database", "cost": 5000.0, "currency": "BRL", "prev_cost": 4800.0, "variation_pct": 4.2},
            {"service": "MySQL Database - Storage", "cost": 2500.0, "currency": "BRL", "prev_cost": 2400.0, "variation_pct": 4.2},
        ]

        recs = OCIFinOpsCollector._build_recommendations([], by_service, [], 30000.0)

        mysql_recs = [r for r in recs if "MySQL" in r["title"] and "storage" in r["detail"].lower()]
        assert len(mysql_recs) == 1
        assert mysql_recs[0]["severity"] == "info"

    def test_multiple_rules_fire_together(self):
        by_compartment = [
            {"compartment": "Application", "cost": 25000.0, "pct": 83.3},
            {"compartment": "Database", "cost": 5000.0, "pct": 16.7},
        ]
        by_service = [
            {"service": "Compute", "cost": 20000.0, "currency": "BRL", "prev_cost": 14000.0, "variation_pct": 42.8},
        ]
        shapes = [
            {"shape_family": "Windows OS Licensing", "ocpu_hours": 12096, "est_ocpus": 18, "cost": 6133.0},
        ]

        recs = OCIFinOpsCollector._build_recommendations(by_compartment, by_service, shapes, 30000.0)

        assert len(recs) >= 3  # windows + concentration + anomaly


class TestAggregateServices:
    """Test that daily usage items are correctly summed per service."""

    def test_sums_daily_items_per_service(self):
        items = [
            _fake_item("Compute", 100.0, "BRL"),
            _fake_item("Compute", 200.0, "BRL"),
            _fake_item("MySQL Database", 50.0, "BRL"),
        ]

        result = OCIFinOpsCollector._aggregate_items_by_key(items, "service")

        assert result["Compute"] == 300.0
        assert result["MySQL Database"] == 50.0

    def test_skips_zero_and_none(self):
        items = [
            _fake_item("Compute", 100.0, "BRL"),
            _fake_item("Compute", 0.0, "BRL"),
            _fake_item("Storage", None, "BRL"),
        ]

        result = OCIFinOpsCollector._aggregate_items_by_key(items, "service")

        assert result["Compute"] == 100.0
        assert "Storage" not in result


class TestAggregateCompartments:
    """Test compartment aggregation."""

    def test_sums_by_compartment(self):
        items = [
            _fake_item("Compute", 100.0, "BRL", compartment="App"),
            _fake_item("MySQL", 50.0, "BRL", compartment="App"),
            _fake_item("Compute", 200.0, "BRL", compartment="DB"),
        ]

        result = OCIFinOpsCollector._aggregate_items_by_key(items, "compartment_name")

        assert result["App"] == 150.0
        assert result["DB"] == 200.0


class TestParseShapeFamily:
    """Test SKU name to shape family parsing."""

    def test_standard_x9(self):
        assert OCIFinOpsCollector._parse_shape_family("Oracle OCPU - Standard - X9 - OCPU Per Hour") == "Standard - X9"

    def test_windows_licensing(self):
        assert OCIFinOpsCollector._parse_shape_family("Windows OS - OCPU Per Hour") == "Windows OS Licensing"

    def test_gpu(self):
        assert OCIFinOpsCollector._parse_shape_family("Oracle OCPU - GPU3 - GPU Per Hour") == "GPU3"

    def test_unknown_sku(self):
        assert OCIFinOpsCollector._parse_shape_family("Some Random SKU") == "Other"


def _fake_item(service, amount, currency, compartment="root"):
    """Helper to create a mock OCI usage item."""
    class FakeItem:
        def __init__(self, svc, amt, cur, comp):
            self.service = svc
            self.computed_amount = amt
            self.currency = cur
            self.compartment_name = comp
            self.sku_name = ""
            self.unit = "OCPU_HOURS"
            self.computed_quantity = amt * 10 if amt else 0
    return FakeItem(service, amount, currency, compartment)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/weekly-report && python -m pytest tests/test_oci_finops_collector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collectors.oci_finops_collector'`

- [ ] **Step 3: Commit test file**

```bash
cd /opt/weekly-report
git add tests/test_oci_finops_collector.py
git commit -m "test: add OCI FinOps collector unit tests"
```

---

## Task 2: OCI FinOps Collector — Implementation

**Files:**
- Create: `collectors/oci_finops_collector.py`

- [ ] **Step 1: Implement OCIFinOpsCollector**

Create `collectors/oci_finops_collector.py`:

```python
"""
Coletor FinOps OCI — breakdown por compartment, servico, compute shape e recomendacoes.
Usa OCI Usage API com group_by dimensions.
"""

import logging
import re
from datetime import datetime, timedelta

import oci
from dateutil.relativedelta import relativedelta
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)


class OCIFinOpsCollector:
    def __init__(self, config: dict):
        self.tenant_id = config["tenant_id"]
        oci_config = oci.config.from_file()
        self.usage_client = oci.usage_api.UsageapiClient(oci_config)

    def collect(self) -> dict:
        """
        Coleta breakdown de custos OCI do mes atual.

        Returns:
            dict com by_compartment, by_service, compute_shapes e recommendations.
        """
        today = datetime.utcnow()
        start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (today + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        prev_start = start - relativedelta(months=1)
        prev_end = start

        # 1. By compartment (current month)
        compartment_items = self._query(start, end, group_by=["compartmentName"])
        compartment_totals = self._aggregate_items_by_key(compartment_items, "compartment_name")
        total_cost = sum(compartment_totals.values())

        by_compartment = [
            {
                "compartment": name,
                "cost": round(cost, 2),
                "pct": round(cost / total_cost * 100, 1) if total_cost > 0 else 0,
            }
            for name, cost in sorted(compartment_totals.items(), key=lambda x: x[1], reverse=True)
        ]

        # 2. By service (current + previous for variation)
        curr_service_items = self._query(start, end, group_by=["service"])
        prev_service_items = self._query(prev_start, prev_end, group_by=["service"])

        curr_services = self._aggregate_items_by_key(curr_service_items, "service")
        prev_services = self._aggregate_items_by_key(prev_service_items, "service")

        currency = "BRL"
        if curr_service_items:
            currency = getattr(curr_service_items[0], "currency", "BRL") or "BRL"

        by_service = []
        for name, cost in sorted(curr_services.items(), key=lambda x: x[1], reverse=True):
            prev_cost = prev_services.get(name, 0)
            variation = round((cost - prev_cost) / prev_cost * 100, 1) if prev_cost > 0 else 0
            by_service.append({
                "service": name,
                "cost": round(cost, 2),
                "currency": currency,
                "prev_cost": round(prev_cost, 2),
                "variation_pct": variation,
            })

        # 3. Compute shapes (current month, Compute service only)
        compute_items = self._query(start, end, group_by=["skuName"], service_filter="Compute")
        shape_totals = {}  # family -> {cost, ocpu_hours}
        for item in compute_items:
            if not item.computed_amount or item.computed_amount <= 0.01:
                continue
            family = self._parse_shape_family(item.sku_name or "")
            entry = shape_totals.setdefault(family, {"cost": 0.0, "ocpu_hours": 0})
            entry["cost"] += item.computed_amount
            if item.computed_quantity:
                entry["ocpu_hours"] += item.computed_quantity

        days_elapsed = max((today - start).days, 1)
        compute_shapes = []
        for family, data in sorted(shape_totals.items(), key=lambda x: x[1]["cost"], reverse=True):
            hours = data["ocpu_hours"]
            est_ocpus = round(hours / (days_elapsed * 24)) if hours > 0 else 0
            compute_shapes.append({
                "shape_family": family,
                "ocpu_hours": round(hours),
                "est_ocpus": est_ocpus,
                "cost": round(data["cost"], 2),
            })

        # 4. Previous month total for variation
        prev_total = sum(prev_services.values())
        variation_pct = round((total_cost - prev_total) / prev_total * 100, 1) if prev_total > 0 else 0

        # 5. Recommendations
        recommendations = self._build_recommendations(by_compartment, by_service, compute_shapes, total_cost)

        return {
            "period": {
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
            },
            "total_cost_brl": round(total_cost, 2),
            "prev_month_cost_brl": round(prev_total, 2),
            "variation_pct": variation_pct,
            "by_compartment": by_compartment,
            "by_service": by_service,
            "compute_shapes": compute_shapes,
            "recommendations": recommendations,
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
           before_sleep=before_sleep_log(logger, logging.WARNING))
    def _query(self, start, end, group_by, service_filter=None):
        """Executa query na Usage API."""
        kwargs = {
            "tenant_id": self.tenant_id,
            "time_usage_started": start,
            "time_usage_ended": end,
            "granularity": "DAILY",
            "query_type": "COST",
            "group_by": group_by,
        }
        if service_filter:
            kwargs["filter"] = oci.usage_api.models.Filter(
                operator="AND",
                dimensions=[
                    oci.usage_api.models.Dimension(key="service", value=service_filter)
                ],
            )
        request = oci.usage_api.models.RequestSummarizedUsagesDetails(**kwargs)
        resp = self.usage_client.request_summarized_usages(request)
        return resp.data.items

    @staticmethod
    def _aggregate_items_by_key(items, key_attr):
        """Agrega computed_amount por atributo (service, compartment_name, etc)."""
        totals = {}
        for item in items:
            amount = item.computed_amount
            if not amount or amount <= 0.001:
                continue
            name = getattr(item, key_attr, None) or "Unknown"
            totals[name] = totals.get(name, 0.0) + amount
        return totals

    @staticmethod
    def _parse_shape_family(sku_name: str) -> str:
        """Extrai familia de shape do nome do SKU OCI."""
        if not sku_name:
            return "Other"
        lower = sku_name.lower()
        if "windows" in lower:
            return "Windows OS Licensing"
        # Pattern: "Oracle OCPU - <Family> - ..." or "Oracle OCPU - <Family>"
        m = re.match(r"Oracle OCPU\s*-\s*(.+?)(?:\s*-\s*(?:OCPU|GPU).*)?$", sku_name, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        # GPU pattern
        m = re.match(r".*?(GPU\d+).*", sku_name, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        return "Other"

    @staticmethod
    def _build_recommendations(by_compartment, by_service, compute_shapes, total_cost):
        """Gera recomendacoes baseadas em regras sobre os dados coletados."""
        recs = []

        # Rule 1: Windows licensing > 10% of total
        for shape in compute_shapes:
            if "windows" in shape["shape_family"].lower():
                if total_cost > 0 and shape["cost"] / total_cost > 0.10:
                    recs.append({
                        "severity": "warning",
                        "title": f"Licenciamento Windows = {shape['cost'] / total_cost * 100:.0f}% do custo total",
                        "detail": f"R$ {shape['cost']:,.2f} em licencas Windows (~{shape['est_ocpus']} OCPUs). Avaliar migracao para Linux onde possivel.",
                        "potential_savings_brl": shape["cost"],
                    })
                break

        # Rule 2: OKE Enhanced clusters detected
        for svc in by_service:
            if "enhanced" in svc["service"].lower() and "kubernetes" in svc["service"].lower():
                recs.append({
                    "severity": "info",
                    "title": "OKE Enhanced Clusters detectados",
                    "detail": f"R$ {svc['cost']:,.2f}/mes em OKE Enhanced. Avaliar se OKE Basic atende aos requisitos.",
                    "potential_savings_brl": round(svc["cost"] * 0.5, 2),
                })
                break

        # Rule 3: Single compartment > 60% of total
        for comp in by_compartment:
            if comp["pct"] > 60:
                recs.append({
                    "severity": "info",
                    "title": f"Concentracao de custo: {comp['compartment']} = {comp['pct']:.0f}%",
                    "detail": f"Compartment '{comp['compartment']}' concentra {comp['pct']:.0f}% do custo total (R$ {comp['cost']:,.2f}). Revisar distribuicao de recursos.",
                    "potential_savings_brl": 0,
                })
                break

        # Rule 4: Any service variation > 30% vs prev month
        for svc in by_service:
            if abs(svc["variation_pct"]) > 30 and svc["prev_cost"] > 100:
                direction = "aumento" if svc["variation_pct"] > 0 else "reducao"
                recs.append({
                    "severity": "warning",
                    "title": f"Anomalia de custo: {svc['service']} ({svc['variation_pct']:+.1f}%)",
                    "detail": f"{direction.capitalize()} de {abs(svc['variation_pct']):.1f}% em {svc['service']}: R$ {svc['prev_cost']:,.2f} -> R$ {svc['cost']:,.2f}.",
                    "potential_savings_brl": round(max(svc["cost"] - svc["prev_cost"], 0), 2),
                })

        # Rule 5: MySQL storage > 40% of MySQL total
        mysql_total = 0
        mysql_storage = 0
        for svc in by_service:
            if "mysql" in svc["service"].lower():
                mysql_total += svc["cost"]
                if "storage" in svc["service"].lower():
                    mysql_storage = svc["cost"]
        if mysql_total > 0 and mysql_storage / mysql_total > 0.40:
            recs.append({
                "severity": "info",
                "title": f"MySQL Storage = {mysql_storage / mysql_total * 100:.0f}% do custo MySQL",
                "detail": f"R$ {mysql_storage:,.2f} em storage MySQL de R$ {mysql_total:,.2f} total. Revisar politicas de retencao e backups.",
                "potential_savings_brl": 0,
            })

        return recs
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /opt/weekly-report && python -m pytest tests/test_oci_finops_collector.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd /opt/weekly-report
git add collectors/oci_finops_collector.py
git commit -m "feat: add OCI FinOps collector with compartment/service/shape breakdown and recommendations"
```

---

## Task 3: Backend Integration — main.py and generator.py

**Files:**
- Modify: `main.py:214` (after OCI collection block)
- Modify: `report/generator.py:26` (generate signature)
- Modify: `report/generator.py:64-76` (report_data dict)

- [ ] **Step 1: Add FinOps collection to main.py**

In `main.py`, after the existing OCI collection block (after line 214, before `# Golden Cloud`), add:

```python
    # OCI FinOps (breakdown detalhado)
    finops_data = None
    if not args.skip_oci and config.get("oci", {}).get("enabled"):
        try:
            from collectors.oci_finops_collector import OCIFinOpsCollector
            logger.info("Coletando OCI FinOps...")
            finops = OCIFinOpsCollector(config["oci"])
            finops_data = finops.collect()
            logger.info("OCI FinOps: %d compartments, %d services, %d recommendations",
                        len(finops_data["by_compartment"]),
                        len(finops_data["by_service"]),
                        len(finops_data["recommendations"]))
        except Exception as e:
            logger.error("OCI FinOps ERRO: %s", e)
            logger.exception("Detalhes:")
```

Then update the `generator.generate(...)` call (line ~282) to pass `finops_data`:

Change:
```python
        result = generator.generate(otrs_data, cloud_costs, monday_boards=monday_boards, otrs_queues=otrs_queues, otrs_daily_queues=[], save_history=not args.refresh, monthly_costs=monthly_costs)
```

To:
```python
        result = generator.generate(otrs_data, cloud_costs, monday_boards=monday_boards, otrs_queues=otrs_queues, otrs_daily_queues=[], save_history=not args.refresh, monthly_costs=monthly_costs, finops_data=finops_data)
```

- [ ] **Step 2: Update generator.py to accept and pass through finops_data**

In `report/generator.py`, update the `generate` method signature (line 26):

Change:
```python
    def generate(self, otrs_data: dict, cloud_costs: list, monday_boards: list = None, otrs_queues: list = None, otrs_daily_queues: list = None, save_history: bool = True, monthly_costs: dict = None) -> dict:
```

To:
```python
    def generate(self, otrs_data: dict, cloud_costs: list, monday_boards: list = None, otrs_queues: list = None, otrs_daily_queues: list = None, save_history: bool = True, monthly_costs: dict = None, finops_data: dict = None) -> dict:
```

In the `report_data` dict construction (around line 75), add after `"monthly_costs"`:

```python
            "finops": finops_data,
```

- [ ] **Step 3: Verify backend runs without errors**

Run: `cd /opt/weekly-report && python main.py --skip-otrs --dry-run 2>&1 | tail -20`
Expected: Should see "Coletando OCI FinOps..." and FinOps stats in the log. `data/report-data.json` should now have a `"finops"` key.

Verify JSON: `python3 -c "import json; d=json.load(open('data/report-data.json')); print('finops' in d, type(d.get('finops')))"`
Expected: `True <class 'dict'>`

- [ ] **Step 4: Commit**

```bash
cd /opt/weekly-report
git add main.py report/generator.py
git commit -m "feat: integrate OCI FinOps collector into main pipeline and report data"
```

---

## Task 4: Frontend Types

**Files:**
- Modify: `/home/ubuntu/weekly-report-hub/src/types/report.ts`

- [ ] **Step 1: Add FinOps interfaces to report.ts**

At the end of the file, before the `ReportData` interface, add:

```typescript
export interface FinOpsCompartment {
  compartment: string;
  cost: number;
  pct: number;
}

export interface FinOpsService {
  service: string;
  cost: number;
  currency: string;
  prev_cost: number;
  variation_pct: number;
}

export interface FinOpsShape {
  shape_family: string;
  ocpu_hours: number;
  est_ocpus: number;
  cost: number;
}

export interface FinOpsRecommendation {
  severity: "warning" | "info";
  title: string;
  detail: string;
  potential_savings_brl: number;
}

export interface FinOpsData {
  period: { start: string; end: string };
  total_cost_brl: number;
  prev_month_cost_brl: number;
  variation_pct: number;
  by_compartment: FinOpsCompartment[];
  by_service: FinOpsService[];
  compute_shapes: FinOpsShape[];
  recommendations: FinOpsRecommendation[];
}
```

Then add `finops?: FinOpsData;` to the `ReportData` interface, after `history`:

```typescript
  finops?: FinOpsData;
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /home/ubuntu/weekly-report-hub && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors (or only pre-existing errors unrelated to FinOps)

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/weekly-report-hub
git add src/types/report.ts
git commit -m "feat: add FinOps type definitions to ReportData"
```

---

## Task 5: Frontend FinOpsTab Component

**Files:**
- Create: `/home/ubuntu/weekly-report-hub/src/components/dashboard/FinOpsTab.tsx`

- [ ] **Step 1: Create FinOpsTab component**

Create `/home/ubuntu/weekly-report-hub/src/components/dashboard/FinOpsTab.tsx`:

```tsx
import { AlertTriangle, Info } from "lucide-react";
import { motion } from "framer-motion";
import KpiCard from "./KpiCard";
import DataTable from "./DataTable";
import type { FinOpsData } from "@/types/report";

interface FinOpsTabProps {
  data?: FinOpsData;
}

const FinOpsTab = ({ data }: FinOpsTabProps) => {
  if (!data) {
    return (
      <div className="bg-card border border-border rounded-lg p-8 text-center">
        <p className="text-muted-foreground text-sm">FinOps indisponivel — dados nao coletados nesta execucao.</p>
      </div>
    );
  }

  const fmt = (v: number) => v.toLocaleString("pt-BR", { minimumFractionDigits: 2 });

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <KpiCard
          label="Custo OCI (mes)"
          value={`R$ ${fmt(data.total_cost_brl)}`}
          delta={data.variation_pct}
          color="primary"
          index={0}
        />
        <KpiCard
          label="Mes Anterior"
          value={`R$ ${fmt(data.prev_month_cost_brl)}`}
          color="primary"
          index={1}
        />
        <KpiCard
          label="Recomendacoes"
          value={data.recommendations.length}
          color={data.recommendations.some((r) => r.severity === "warning") ? "warning" : "success"}
          index={2}
        />
      </div>

      {/* By Compartment */}
      <DataTable
        title="Custo por Compartment"
        columns={[
          { key: "compartment", label: "Compartment", render: (v: string) => <span className="font-semibold">{v}</span> },
          { key: "cost", label: "Custo (R$)", align: "right", render: (v: number) => fmt(v) },
          { key: "pct", label: "% Total", align: "right", render: (v: number) => `${v.toFixed(1)}%` },
        ]}
        data={data.by_compartment}
      />

      {/* By Service */}
      <DataTable
        title="Custo por Servico"
        columns={[
          { key: "service", label: "Servico", render: (v: string) => <span className="font-semibold">{v}</span> },
          { key: "cost", label: "Custo (R$)", align: "right", render: (v: number) => fmt(v) },
          { key: "prev_cost", label: "Mes Anterior", align: "right", render: (v: number) => fmt(v) },
          {
            key: "variation_pct",
            label: "Variacao",
            align: "right",
            render: (v: number) => (
              <span className={v > 30 ? "text-destructive font-semibold" : v < -10 ? "text-success font-semibold" : ""}>
                {v > 0 ? "+" : ""}{v.toFixed(1)}%
              </span>
            ),
          },
        ]}
        data={data.by_service}
      />

      {/* Compute Shapes */}
      {data.compute_shapes.length > 0 && (
        <DataTable
          title="Compute — Shapes"
          columns={[
            { key: "shape_family", label: "Shape Family", render: (v: string) => <span className="font-semibold">{v}</span> },
            { key: "est_ocpus", label: "Est. OCPUs", align: "right" },
            { key: "ocpu_hours", label: "OCPU-Hours", align: "right", render: (v: number) => v.toLocaleString("pt-BR") },
            { key: "cost", label: "Custo (R$)", align: "right", render: (v: number) => fmt(v) },
          ]}
          data={data.compute_shapes}
        />
      )}

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground">Recomendacoes</h3>
          {data.recommendations.map((rec, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.08 }}
              className={`border rounded-lg p-4 ${
                rec.severity === "warning"
                  ? "border-warning/50 bg-warning/5"
                  : "border-primary/30 bg-primary/5"
              }`}
            >
              <div className="flex items-start gap-3">
                {rec.severity === "warning" ? (
                  <AlertTriangle className="w-4 h-4 text-warning mt-0.5 shrink-0" />
                ) : (
                  <Info className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                )}
                <div>
                  <p className="text-sm font-semibold text-foreground">{rec.title}</p>
                  <p className="text-xs text-muted-foreground mt-1">{rec.detail}</p>
                  {rec.potential_savings_brl > 0 && (
                    <p className="text-xs font-semibold text-success mt-1">
                      Economia potencial: R$ {fmt(rec.potential_savings_brl)}
                    </p>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FinOpsTab;
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /home/ubuntu/weekly-report-hub && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/weekly-report-hub
git add src/components/dashboard/FinOpsTab.tsx
git commit -m "feat: add FinOpsTab component with KPIs, tables, and recommendation cards"
```

---

## Task 6: Wire FinOpsTab into CloudTab

**Files:**
- Modify: `/home/ubuntu/weekly-report-hub/src/components/dashboard/CloudTab.tsx`

- [ ] **Step 1: Add import and sub-tab entry**

At the top of `CloudTab.tsx`, add the import (after existing imports):

```typescript
import FinOpsTab from "./FinOpsTab";
```

Add the FinOps sub-tab to `cloudSubTabs`:

Change:
```typescript
const cloudSubTabs = [
  { id: "chamados", label: "Chamados Cloud" },
  { id: "custos", label: "Custos Cloud" },
  { id: "projetos", label: "Projetos" },
];
```

To:
```typescript
const cloudSubTabs = [
  { id: "chamados", label: "Chamados Cloud" },
  { id: "custos", label: "Custos Cloud" },
  { id: "finops", label: "FinOps OCI" },
  { id: "projetos", label: "Projetos" },
];
```

- [ ] **Step 2: Add FinOps rendering section**

After the `{subTab === "custos" && (` block (after its closing `)}`) and before `{subTab === "projetos"`, add:

```tsx
      {subTab === "finops" && <FinOpsTab data={data.finops} />}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /home/ubuntu/weekly-report-hub && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/weekly-report-hub
git add src/components/dashboard/CloudTab.tsx
git commit -m "feat: wire FinOps OCI sub-tab into CloudTab"
```

---

## Task 7: Build and Deploy Frontend

**Files:**
- No new files — build output to `/var/www/html/dashboard/`

- [ ] **Step 1: Build the React app**

Run: `cd /home/ubuntu/weekly-report-hub && npm run build 2>&1 | tail -10`
Expected: Build succeeds, output in `dist/`

- [ ] **Step 2: Deploy to nginx**

```bash
cp -r /home/ubuntu/weekly-report-hub/dist/* /var/www/html/dashboard/
```

- [ ] **Step 3: Refresh backend data so report-data.json includes finops**

Run: `cd /opt/weekly-report && python main.py --skip-otrs --dry-run 2>&1 | tail -10`
Expected: "OCI FinOps: X compartments, Y services, Z recommendations"

- [ ] **Step 4: Verify dashboard loads in browser**

Run: `curl -s http://127.0.0.1:8080/dashboard/api/report-data | python3 -c "import json,sys; d=json.load(sys.stdin); f=d.get('finops',{}); print(f'finops keys: {list(f.keys()) if f else \"null\"}')" 2>&1`
Expected: `finops keys: ['period', 'total_cost_brl', 'prev_month_cost_brl', 'variation_pct', 'by_compartment', 'by_service', 'compute_shapes', 'recommendations']`

- [ ] **Step 5: Commit (both repos)**

```bash
cd /opt/weekly-report
git add -A
git commit -m "feat: deploy FinOps OCI — backend + frontend build"
```

---

## Task 8: Restart Service and End-to-End Verification

- [ ] **Step 1: Restart the API service**

```bash
sudo systemctl restart weekly-report-api
```

- [ ] **Step 2: Verify API serves finops data**

Run: `curl -s http://127.0.0.1:8080/dashboard/api/report-data | python3 -c "import json,sys; d=json.load(sys.stdin); f=d['finops']; print(f'Total: R$ {f[\"total_cost_brl\"]:,.2f}'); print(f'Compartments: {len(f[\"by_compartment\"])}'); print(f'Services: {len(f[\"by_service\"])}'); print(f'Shapes: {len(f[\"compute_shapes\"])}'); print(f'Recommendations: {len(f[\"recommendations\"])}')" 2>&1`
Expected: Shows OCI FinOps summary with real data

- [ ] **Step 3: Verify dashboard HTML loads**

Run: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/dashboard/`
Expected: `200`

- [ ] **Step 4: Run all backend tests**

Run: `cd /opt/weekly-report && python -m pytest tests/ -v 2>&1`
Expected: All tests pass
