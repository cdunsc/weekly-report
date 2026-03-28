#!/usr/bin/env python3
"""
Reconstrói o histórico semanal (sex-qui) desde janeiro/2026 com dados reais.
- OTRS: via CSV exportado por scraping
- AWS: Cost Explorer (month-to-date acumulado até cada quinta)
- OCI: Usage API (month-to-date acumulado até cada quinta)
- Golden Cloud: sem histórico, marcado como N/A
"""

import csv
import io
import json
import os
import sys
from datetime import datetime, timedelta

import boto3
import oci
import requests
import yaml

CONFIG_FILE = "/opt/weekly-report/config.yaml"
DATA_DIR = "/opt/weekly-report/data"
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

CLOSED_STATES = {
    "Fechado com êxito", "Fechado sem êxito", "fechado",
    "fechado com êxito", "fechado sem êxito",
    "fechado com solução de contorno", "Encerrado",
    "Resolvido", "Indevido",
}


def load_config():
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def get_weekly_periods(start_date_str="2026-01-02", end_date_str=None):
    """
    Gera períodos sex-qui desde start_date até agora.
    A primeira quinta de janeiro 2026 é 01/01 (qui),
    então a primeira semana completa é sex 02/01 a qui 08/01.
    """
    if end_date_str:
        end_limit = datetime.strptime(end_date_str, "%Y-%m-%d")
    else:
        end_limit = datetime.now()

    # Encontra a primeira sexta-feira >= start_date
    current = datetime.strptime(start_date_str, "%Y-%m-%d")
    while current.weekday() != 4:  # 4 = sexta
        current += timedelta(days=1)

    periods = []
    while current + timedelta(days=6) <= end_limit:
        friday = current
        thursday = current + timedelta(days=6)
        periods.append((friday.strftime("%Y-%m-%d"), thursday.strftime("%Y-%m-%d")))
        current += timedelta(days=7)

    return periods


def fetch_otrs_csv_queue(config, queue_name, queue_id):
    """Login no OTRS e exporta CSV de todos os tickets de uma fila."""
    import re

    session = requests.Session()
    panel_url = config["otrs"]["panel_url"]

    # Login
    resp = session.post(
        f"{panel_url}/otrs/index.pl",
        data={
            "Action": "Login",
            "RequestedURL": "",
            "Lang": "pt_BR",
            "TimeOffset": "180",
            "User": config["otrs"]["username"],
            "Password": config["otrs"]["password"],
        },
        allow_redirects=True,
        timeout=30,
    )

    if "LoginFailed" in resp.url:
        raise RuntimeError("Falha no login OTRS")

    token = re.search(r'ChallengeToken=([a-zA-Z0-9]+)', resp.text).group(1)

    # Export CSV
    print(f"[OTRS] Exportando CSV da fila {queue_name} (ID={queue_id})...")
    resp = session.post(
        f"{panel_url}/otrs/index.pl",
        data={
            "Action": "AgentTicketSearch",
            "Subaction": "Search",
            "ChallengeToken": token,
            "QueueIDs": str(queue_id),
            "ResultForm": "CSV",
            "SortBy": "Age",
            "OrderBy": "Down",
        },
        timeout=120,
    )
    resp.raise_for_status()

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content), delimiter=";")
    header = next(reader)
    col_map = {name: i for i, name in enumerate(header)}

    tickets = []
    for row in reader:
        if len(row) < len(header):
            continue
        tickets.append({
            "number": row[col_map.get("Número do Chamado", 0)],
            "created": row[col_map.get("Criado", 2)],
            "closed": row[col_map.get("Fechado", 3)],
            "state": row[col_map.get("Estado", 6)],
            "first_response_minutes": row[col_map.get("Primeira Resposta em Minutos", 21)],
            "resolution_minutes": row[col_map.get("Tempo de solução em minutos", 19)],
        })

    print(f"[OTRS] {queue_name}: {len(tickets)} tickets carregados")
    return tickets


def fetch_all_queues(config):
    """Exporta tickets de todas as filas configuradas."""
    queues = config["otrs"].get("queues", [{"name": "CLOUD", "queue_id": 26}])
    all_queues = {}
    for q in queues:
        tickets = fetch_otrs_csv_queue(config, q["name"], q["queue_id"])
        all_queues[q["name"]] = tickets
    return all_queues


def calc_otrs_metrics(tickets, start_date, end_date,
                      sla_first_response_hours=24, sla_resolution_hours=72):
    """Calcula métricas OTRS para um período sex-qui."""
    start_ts = f"{start_date} 00:00:00"
    end_ts = f"{end_date} 23:59:59"

    opened = [t for t in tickets if start_ts <= t["created"] <= end_ts]
    closed = [t for t in tickets if t["closed"] and start_ts <= t["closed"] <= end_ts]

    # Backlog: tickets criados até end_date que NÃO estavam fechados até end_date
    # Um ticket está no backlog se: foi criado <= end_date E (não tem data de fechamento OU foi fechado depois de end_date)
    backlog = [
        t for t in tickets
        if t["created"] <= end_ts
        and (not t["closed"] or t["closed"] > end_ts)
        and t["state"] not in CLOSED_STATES  # fallback para estado atual se ticket antigo
    ]
    # Método mais preciso: contar tickets que estavam abertos no final da quinta
    backlog_count = 0
    for t in tickets:
        if t["created"] <= end_ts:
            if not t["closed"] or t["closed"] > end_ts:
                backlog_count += 1

    # SLA
    fr_hours = []
    for t in opened:
        val = t["first_response_minutes"].strip()
        if val:
            try:
                fr_hours.append(round(float(val) / 60, 2))
            except ValueError:
                pass

    res_hours = []
    for t in opened:
        val = t["resolution_minutes"].strip()
        if val:
            try:
                res_hours.append(round(float(val) / 60, 2))
            except ValueError:
                pass

    avg_fr = round(sum(fr_hours) / len(fr_hours), 2) if fr_hours else None
    avg_res = round(sum(res_hours) / len(res_hours), 2) if res_hours else None

    # Percentual dentro do SLA
    fr_within = sum(1 for h in fr_hours if h <= sla_first_response_hours)
    res_within = sum(1 for h in res_hours if h <= sla_resolution_hours)
    pct_fr = round(fr_within / len(fr_hours) * 100, 1) if fr_hours else None
    pct_res = round(res_within / len(res_hours) * 100, 1) if res_hours else None

    return {
        "opened": len(opened),
        "closed": len(closed),
        "backlog": backlog_count,
        "avg_first_response": avg_fr,
        "avg_resolution": avg_res,
        "pct_first_response": pct_fr,
        "pct_resolution": pct_res,
    }


def fetch_aws_monthly_costs():
    """Busca custos diários AWS de janeiro até hoje."""
    print("[AWS] Buscando custos diários desde janeiro...")
    client = boto3.client("ce", region_name="us-east-1")

    start = "2026-01-01"
    end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    resp = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
    )

    # daily_costs[date_str] = cost_usd
    daily_costs = {}
    for result in resp.get("ResultsByTime", []):
        date = result["TimePeriod"]["Start"]
        amount = float(result["Total"]["UnblendedCost"]["Amount"])
        daily_costs[date] = amount

    # Handle pagination
    while resp.get("NextPageToken"):
        resp = client.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            NextPageToken=resp["NextPageToken"],
        )
        for result in resp.get("ResultsByTime", []):
            date = result["TimePeriod"]["Start"]
            amount = float(result["Total"]["UnblendedCost"]["Amount"])
            daily_costs[date] = amount

    print(f"[AWS] {len(daily_costs)} dias de custo carregados")
    return daily_costs


def fetch_oci_monthly_costs(config):
    """Busca custos diários OCI de janeiro até hoje."""
    print("[OCI] Buscando custos diários desde janeiro...")
    tenant_id = config["oci"]["tenant_id"]
    oci_config = oci.config.from_file()
    client = oci.usage_api.UsageapiClient(oci_config)

    start = datetime(2026, 1, 1)
    end = datetime.utcnow() + timedelta(days=1)
    end = end.replace(hour=0, minute=0, second=0, microsecond=0)

    request = oci.usage_api.models.RequestSummarizedUsagesDetails(
        tenant_id=tenant_id,
        time_usage_started=start,
        time_usage_ended=end,
        granularity="DAILY",
        query_type="COST",
    )

    resp = client.request_summarized_usages(request)

    daily_costs = {}
    currency = "BRL"
    for item in resp.data.items:
        if item.computed_amount is not None:
            date = item.time_usage_started.strftime("%Y-%m-%d")
            daily_costs[date] = daily_costs.get(date, 0.0) + item.computed_amount
            currency = item.currency or currency

    print(f"[OCI] {len(daily_costs)} dias de custo carregados (moeda: {currency})")
    return daily_costs, currency


def calc_mtd_cost(daily_costs, thursday_date):
    """Calcula custo month-to-date até a quinta-feira (inclusive)."""
    thu = datetime.strptime(thursday_date, "%Y-%m-%d")
    month_start = thu.replace(day=1)

    total = 0.0
    current = month_start
    while current <= thu:
        date_str = current.strftime("%Y-%m-%d")
        total += daily_costs.get(date_str, 0.0)
        current += timedelta(days=1)

    return round(total, 2)


def main():
    config = load_config()

    # Últimos 3 meses (~13 semanas)
    three_months_ago = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    periods = get_weekly_periods(three_months_ago)

    print(f"Períodos a processar: {len(periods)} (últimos 3 meses)")
    for p in periods:
        print(f"  {p[0]} (sex) → {p[1]} (qui)")
    print()

    # 1. OTRS — todas as filas
    all_queues = fetch_all_queues(config)
    # SLAs por fila (do config)
    queue_slas = {}
    for q in config["otrs"].get("queues", []):
        queue_slas[q["name"]] = {
            "sla_first_response_hours": q.get("sla_first_response_hours", 24),
            "sla_resolution_hours": q.get("sla_resolution_hours", 72),
        }

    # 2. AWS
    aws_daily = fetch_aws_monthly_costs()

    # 3. OCI
    oci_daily, oci_currency = fetch_oci_monthly_costs(config)

    # 4. Monta histórico
    history = []
    for start, end in periods:
        # Métricas por fila
        queues_snapshot = {}
        first_queue_metrics = None
        for queue_name, tickets in all_queues.items():
            sla = queue_slas.get(queue_name, {})
            metrics = calc_otrs_metrics(
                tickets, start, end,
                sla_first_response_hours=sla.get("sla_first_response_hours", 24),
                sla_resolution_hours=sla.get("sla_resolution_hours", 72),
            )
            queues_snapshot[queue_name] = metrics
            if first_queue_metrics is None:
                first_queue_metrics = metrics

        aws_cost = calc_mtd_cost(aws_daily, end)
        oci_cost = calc_mtd_cost(oci_daily, end)

        entry = {
            "date": datetime.strptime(end, "%Y-%m-%d").strftime("%d/%m/%Y") + " 11:00",
            "period": {"start": start, "end": end},
            # Campos legados (primeira fila para compatibilidade)
            "opened": first_queue_metrics["opened"] if first_queue_metrics else 0,
            "closed": first_queue_metrics["closed"] if first_queue_metrics else 0,
            "backlog": first_queue_metrics["backlog"] if first_queue_metrics else 0,
            "avg_first_response": first_queue_metrics["avg_first_response"] if first_queue_metrics else None,
            "avg_resolution": first_queue_metrics["avg_resolution"] if first_queue_metrics else None,
            "cloud_costs": {
                "AWS": aws_cost,
                "OCI": oci_cost,
            },
            "queues": queues_snapshot,
        }

        for qn, qm in queues_snapshot.items():
            print(f"  [{start} → {end}] {qn}: Abertos={qm['opened']}, Fechados={qm['closed']}, "
                  f"Backlog={qm['backlog']}, 1ªResp={qm['pct_first_response']}%, Resol={qm['pct_resolution']}%")

        print(f"  AWS: ${aws_cost:,.0f}, OCI: R${oci_cost:,.0f}")

        history.append(entry)

    # Salva
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Histórico salvo em {HISTORY_FILE} com {len(history)} semanas")


if __name__ == "__main__":
    main()
