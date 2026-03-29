# FinOps OCI — Design Spec

## Goal

Add a "FinOps" sub-tab to the Cloud tab in the weekly report dashboard, showing cost breakdown by compartment, service, compute shape family, monthly trends, and automated recommendations — all derived from the OCI Usage/Cost API (no instance-level permissions needed).

## Architecture

New collector (`oci_finops_collector.py`) queries the Usage API with `group_by` dimensions to build cost breakdowns. It generates a `finops_data` dict that gets included in `report_data` alongside existing cloud cost data. The React frontend adds a "FinOps" sub-tab to `CloudTab` that renders this data.

## Backend: `collectors/oci_finops_collector.py`

Single class `OCIFinOpsCollector` with methods:

### `collect() -> dict`

Returns:

```python
{
    "period": {"start": "2026-03-01", "end": "2026-03-29"},
    "total_cost_brl": 30658.0,
    "prev_month_cost_brl": 25433.62,
    "variation_pct": 20.5,

    "by_compartment": [
        {"compartment": "Application", "cost": 20426.0, "pct": 66.6},
        {"compartment": "Database", "cost": 3437.0, "pct": 11.2},
        ...
    ],

    "by_service": [
        {"service": "Compute", "cost": 20057.0, "currency": "BRL", "prev_cost": 17200.0, "variation_pct": 16.6},
        {"service": "MySQL Database", "cost": 5970.0, "currency": "BRL", "prev_cost": 5800.0, "variation_pct": 2.9},
        ...
    ],

    "compute_shapes": [
        {"shape_family": "Standard - X9", "ocpu_hours": 27552, "est_ocpus": 40, "cost": 7263.0},
        {"shape_family": "Windows OS Licensing", "ocpu_hours": 12096, "est_ocpus": 18, "cost": 6133.0},
        ...
    ],

    "recommendations": [
        {
            "severity": "warning",
            "title": "Licenciamento Windows = 20% do custo total",
            "detail": "R$ 6.133 em licencas Windows (~18 OCPUs). Avaliar migracao para Linux onde possivel.",
            "potential_savings_brl": 6133.0
        },
        ...
    ]
}
```

### Data sources (all via Usage API)

1. **By compartment:** `group_by=["compartmentName"]`, current month, `granularity=MONTHLY`
2. **By service:** `group_by=["service"]`, current month + previous month for variation
3. **Compute shapes:** `group_by=["skuName"]`, filtered to Compute service, parse shape family from SKU name
4. **Recommendations:** Generated from rules applied to the data above

### Recommendation rules

| Condition | Severity | Message |
|---|---|---|
| Windows licensing > 10% of total | warning | Suggest Linux migration |
| OKE Enhanced clusters detected | info | Suggest evaluating OKE Basic |
| Single compartment > 60% of total | info | Cost concentration risk |
| Any service variation > 30% vs prev month | warning | Cost anomaly alert |
| MySQL storage > 40% of MySQL total | info | Review storage/retention |

## Backend: Integration with `main.py`

After existing OCI cost collection, add:

```python
if not args.skip_oci and config.get("oci", {}).get("enabled"):
    try:
        from collectors.oci_finops_collector import OCIFinOpsCollector
        finops = OCIFinOpsCollector(config["oci"])
        finops_data = finops.collect()
    except Exception as e:
        logger.error("OCI FinOps ERRO: %s", e)
        finops_data = None
```

Pass `finops_data` to `generator.generate()` and include in `report_data`.

## Frontend: Types

Add to `src/types/report.ts`:

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

Add `finops?: FinOpsData` to `ReportData` interface.

## Frontend: CloudTab changes

Add `{ id: "finops", label: "FinOps OCI" }` to `cloudSubTabs`.

New `subTab === "finops"` section renders:

1. **KPI cards row:** Total OCI cost, variation %, # recommendations
2. **DataTable:** Cost by compartment (compartment, cost R$, % total)
3. **DataTable:** Cost by service (service, cost R$, prev cost, variation %)
4. **DataTable:** Compute shape breakdown (shape family, est. OCPUs, cost R$)
5. **Recommendations cards:** Each recommendation as a card with severity color (warning=yellow, info=blue), title bold, detail text, potential savings

## Error handling

- If FinOps collector fails, `finops_data` is `null` in the JSON
- Frontend shows "FinOps indisponivel" message when `data.finops` is undefined
- The sub-tab still appears (so user knows it exists) but shows a placeholder

## No changes to

- Existing OCI cost collector (it continues working for the Custos Cloud sub-tab)
- Email/Teams delivery (FinOps is dashboard-only for now)
- Authentication or API routes
