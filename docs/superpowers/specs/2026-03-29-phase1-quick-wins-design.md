# Fase 1: Quick Wins Operacionais — Design Spec

## Goal

Add 4 operational improvements to the weekly report: cost forecasting, cloud efficiency score, structured JSON logging, and collector duration metrics.

## 1. Forecast de Custo Mensal

### Backend: `report/generator.py`

New method `_calc_forecasts(cloud_costs, dollar_rate)` called during `generate()`. For each provider + total:

```python
{
    "forecasts": {
        "AWS": {"accumulated_brl": 95000.0, "estimated_brl": 108500.0, "days_elapsed": 29, "days_total": 31},
        "OCI": {"accumulated_brl": 31326.0, "estimated_brl": 33500.0, "days_elapsed": 29, "days_total": 31},
        "Golden Cloud": {"accumulated_brl": 37729.0, "estimated_brl": 40300.0, "days_elapsed": 29, "days_total": 31},
        "total": {"accumulated_brl": 164055.0, "estimated_brl": 182300.0, "days_elapsed": 29, "days_total": 31}
    }
}
```

Logic:
- `days_elapsed = today.day` (or from period start to today)
- `days_total = calendar.monthrange(year, month)[1]`
- `estimated_brl = accumulated_brl / days_elapsed * days_total`
- All values in BRL (USD costs already converted by this point)

Added to `report_data` dict alongside existing fields.

### Frontend: CloudTab custos sub-tab

Add a row of KPI cards below existing cost cards showing forecast:
- One card per provider: "Est. Fechamento AWS: R$ 108.500"
- One total card: "Est. Total: R$ 182.300"
- Use `meta` field to show "baseado em N dias"

### Teams/Email

Add "Est. Fechamento" column to the cost table in Teams Adaptive Card and email template.

## 2. Cloud Efficiency Score

### Backend: `report/generator.py`

New method `_calc_efficiency_score(report_data)` called after all other data is assembled. Returns int 0-100 or None.

Rules (start at 100, deduct):

| Condition | Source | Deduction |
|-----------|--------|-----------|
| Windows licensing > 10% of OCI total | `finops.recommendations` | -15 |
| Single compartment > 60% | `finops.recommendations` | -10 |
| Any service variation > 30% | `finops.recommendations` | -10 per service, max -20 |
| OKE Enhanced detected | `finops.recommendations` | -5 |
| MySQL storage > 40% of MySQL total | `finops.recommendations` | -5 |
| SLA 1a resposta < 90% | `otrs_queues[0].pct_first_response` | -10 |
| SLA resolucao < 90% | `otrs_queues[0].pct_resolution` | -10 |

If `finops` is None, score is None (not displayed). Minimum score: 0.

Implementation: iterate over `finops["recommendations"]` and check severity/title patterns to count deductions. For SLA, check the first queue (CLOUD).

Added as `efficiency_score` (int or null) to `report_data`.

### Frontend: CloudTab custos sub-tab

Single large KPI card at the top of the custos view: "Efficiency Score: 75/100". Color: green (>=80), warning (60-79), destructive (<60).

### Teams

Add to header: "Score: 75/100" next to period.

## 3. Logs Estruturados JSON

### Backend: `log_config.py`

Replace current formatter with JSON formatter. Each log line becomes:

```json
{"timestamp": "2026-03-29T09:00:01.234", "level": "INFO", "module": "main", "message": "Coletando custos AWS..."}
```

Implementation: custom `logging.Formatter` subclass that outputs JSON. Uses `json.dumps` with fields: timestamp, level, module (logger name), message. No external dependency needed.

Keep console output human-readable when running interactively (detect if stdout is a TTY). Use JSON format for file/service output only.

## 4. Metricas de Duracao dos Coletores

### Backend: `main.py`

Wrap each collector call with `time.time()` before/after. Build dict:

```python
collector_metrics = {
    "collectors": {
        "otrs": {"status": "ok", "duration_s": 2.1},
        "aws": {"status": "ok", "duration_s": 3.2},
        "oci": {"status": "ok", "duration_s": 4.1},
        "oci_finops": {"status": "ok", "duration_s": 8.5},
        "golden_cloud": {"status": "ok", "duration_s": 62.3},
        "monday": {"status": "ok", "duration_s": 5.4},
    },
    "total_s": 85.6
}
```

Status values: "ok", "error", "skip". Pass to generator, include in `report_data`.

### Frontend

Small DataTable at the bottom of the dashboard page (visible on all tabs) or as a collapsible section. Columns: Collector, Status, Duration.

## No changes to

- Existing collector logic (only timing wrapper in main.py)
- Authentication or API routes
- History format (forecasts/score are ephemeral, not persisted in history)
- Cron schedule
