# Operational Improvements v2 — Design Spec

## Goal

Enrich all delivery channels (Teams, email, dashboard) with trend indicators, cost anomaly alerts, and Monday.com progress visualization. Data already exists in `report_data` — this is primarily a rendering/template effort.

## Guiding Principles

- **Email/Teams = glanceable executive summary** with deltas and top accounts
- **Dashboard = operational depth** with visual trend badges and anomaly alerts
- **Email stays light theme** (compatibility with Outlook/Gmail)
- **No new data collection** — everything uses existing `report_data["deltas"]`, `cloud_details`, `monday_boards`

---

## 1. Teams Adaptive Card — Deltas and Monday.com Progress

### 1.1 Cost Deltas

Each provider row in the cost table gains a delta indicator in the "Custo (BRL)" cell.

**Current:** `BRL 805,219.41`
**New:** `BRL 805,219.41 ▲ +12.1%`

The TOTAL row also gets a delta.

Data source: `report_data["deltas"]["cost_AWS"]`, `report_data["deltas"]["cost_total"]`, etc. Each has `{"current", "previous", "pct"}`.

Rules:
- If `pct > 0`: `▲ +{pct}%`
- If `pct < 0`: `▼ {pct}%`
- If `pct == 0` or no previous data: omit indicator

### 1.2 Ticket Deltas

Each ticket metric (Abertos, Fechados, Backlog) gains an inline delta.

**Current:** `18`
**New:** `18 (▲ +3)`

Data source: `report_data["deltas"]["CLOUD_opened"]`, etc.

### 1.3 Top 3 AWS Accounts

After the cost table, add a small section showing the top 3 AWS accounts by cost. Only if AWS data has `accounts` field.

Format: TextBlock list, e.g.:
```
💰 Top Contas AWS:
  1. Production — USD 89,432.10
  2. Data Lake — USD 34,211.55
  3. Staging — USD 12,098.77
```

Data source: `report_data["clouds"]` where `provider == "AWS"`, field `accounts` (already sorted by cost desc).

### 1.4 Monday.com Progress

Replace current simple table (Board/Total/Concluidos) with a richer table:

| Board | Total | Feitos | % |
|-------|-------|--------|---|
| Projetos Cloud | 12 | 8 | 67% |
| Projetos TI | 9 | 3 | 33% |

The `%` column = `done / total * 100`, rounded to integer.

Data source: existing `monday_boards[].status_summary` (count "Feito"/"Concluido"/"Done") and `total_projects`.

---

## 2. Email Template — Deltas, Top Accounts, Monday.com

### 2.1 Ticket Deltas

Each metric in the chamados table gains an inline delta in parentheses.

**Current:** `<td>18</td>`
**New:** `<td>18 <span style="color: #ef4444; font-size: 0.85em;">(▲ +3)</span></td>`

Color rules for tickets:
- Abertos: gray (neutral)
- Fechados: green if up, red if down
- Backlog: red if up, green if down
- SLA %: green if up, red if down

### 2.2 Cost Deltas

Each provider row gains delta indicator after the BRL value.

Color rules for costs:
- Up = red (#ef4444)
- Down = green (#22c55e)

### 2.3 Top 5 AWS Accounts

New table below the costs section, only rendered if AWS accounts data exists:

```html
<h3>Top Contas AWS</h3>
<table>
  <tr><th>Conta</th><th>Custo (USD)</th></tr>
  <tr><td>Production</td><td>89,432.10</td></tr>
  ...
</table>
```

Show top 5 from `clouds[provider=="AWS"]["accounts"]`.

### 2.4 Monday.com Projects Section

New section after costs, before the CTA button:

```html
<h3>Projetos</h3>
<table>
  <tr><th>Board</th><th>Total</th><th>Concluidos</th><th>Progresso</th></tr>
  <tr>
    <td>Projetos Cloud</td>
    <td>12</td>
    <td>8</td>
    <td>
      <div style="background:#e5e7eb;border-radius:4px;height:8px;width:100px;">
        <div style="background:#22c55e;height:8px;border-radius:4px;width:67%;"></div>
      </div>
    </td>
  </tr>
</table>
```

Progress bar is a simple CSS inline div (no JS needed, email-safe).

---

## 3. Dashboard — KPI Delta Badges

### 3.1 Badge Design

Each KPI card gets a small badge in the top-right corner:

```
┌─────────────────────┐
│  Abertos    ▲ +12%  │
│     18               │
└─────────────────────┘
```

CSS class: `.kpi-delta` — absolute positioned top-right of the card.

Colors by context:
- **Costs** (AWS, OCI, Golden, Total): up = `#ef4444` (red), down = `#22c55e` (green)
- **Fechados**: up = green, down = red
- **Backlog**: up = red, down = green
- **Abertos**: always `#94a3b8` (gray) — neutral
- **SLA %**: up = green, down = red

### 3.2 Data Binding

The deltas dict uses keys like `cost_AWS`, `cost_total`, `CLOUD_opened`, `CLOUD_closed`, `CLOUD_backlog`.

In the Jinja2 template, for each KPI card:
```jinja2
{% set delta = deltas.get("CLOUD_opened", {}) %}
{% if delta and delta.pct is defined %}
  <span class="kpi-delta" style="color: #94a3b8;">
    {{ "▲" if delta.pct > 0 else "▼" }} {{ "%+.1f"|format(delta.pct) }}%
  </span>
{% endif %}
```

### 3.3 Where Badges Appear

- **Cloud tab > Chamados**: Abertos, Fechados, Backlog cards
- **Cloud tab > Custos**: per-provider cards + Total card
- **TI tab > Chamados**: same pattern for TI queue
- **TI tab > Custos**: same cost cards (they're shared)

---

## 4. Dashboard — Cost Anomaly Banner

### 4.1 Trigger

Show banner if any provider delta > 20% or < -20%.

### 4.2 Design

Yellow/amber banner at the top of the costs section:

```
⚠️ AWS: variacao de +23.4% vs semana anterior
```

If multiple providers have anomalies, show one line per provider.

### 4.3 Data

From `report_data["deltas"]`, check each `cost_{provider}` entry. If `abs(pct) > 20`, include in banner.

### 4.4 Template

```jinja2
{% set anomalies = [] %}
{% for key, val in deltas.items() %}
  {% if key.startswith("cost_") and key != "cost_total" and val.pct is defined and (val.pct > 20 or val.pct < -20) %}
    {% set provider = key.replace("cost_", "") %}
    {% do anomalies.append({"provider": provider, "pct": val.pct}) %}
  {% endif %}
{% endfor %}
{% if anomalies %}
<div class="anomaly-banner">
  {% for a in anomalies %}
    ⚠️ {{ a.provider }}: variacao de {{ "%+.1f"|format(a.pct) }}% vs semana anterior
  {% endfor %}
</div>
{% endif %}
```

CSS: amber background, dark text, rounded corners, top of costs section.

---

## 5. Dashboard — Monday.com Progress Bars (All Tabs)

### 5.1 Current State

The Security tab already has a consolidated KPI grid with status counts and a stacked progress bar. Cloud and TI tabs show project tables but no progress summary.

### 5.2 Enhancement

Add a summary row above each board's project table (Cloud and TI tabs):

```
[████████████░░░░░░░░] 67% concluido (8/12)
 ■ Feito  ■ Em Progresso  ■ Parado  ■ Nao Iniciado
```

Stacked bar uses the same color scheme as Security tab for consistency:
- Green (#22c55e): Feito/Concluido/Done
- Blue (#3b82f6): Em Progresso/Trabalhando nisso
- Red (#ef4444): Parado/Stuck
- Gray (#6b7280): Nao Iniciado/everything else

### 5.3 Data

Already available in `monday_boards[].status_summary` dict.

---

## Files to Modify

| File | Changes |
|------|---------|
| `delivery/teams_sender.py` | Add deltas to cost/ticket rows, top 3 AWS accounts, Monday.com % column |
| `report/templates/email.html` | Add deltas inline, top 5 AWS accounts table, Monday.com section with progress bars |
| `report/templates/dashboard.html` | Add KPI delta badges, anomaly banner, progress bars on Cloud/TI tabs |
| `static/css/dashboard.css` | Add `.kpi-delta`, `.anomaly-banner`, progress bar styles |
| `report/generator.py` | Minor: ensure `deltas` and `cloud_details` are always in report_data (even if empty) |

No new files. No new dependencies. No new data collection.
