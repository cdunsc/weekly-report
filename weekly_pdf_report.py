#!/usr/bin/env python3
"""
Relatorio Semanal PDF - Surf Telecom
Coleta dados da semana (sexta a quinta), gera PDF e envia por e-mail.

Uso:
    python weekly_pdf_report.py
    python weekly_pdf_report.py --dry-run
    python weekly_pdf_report.py --start 2026-03-27 --end 2026-04-02
    python weekly_pdf_report.py --to email1 --to email2
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import yaml

from env_loader import inject_secrets
from log_config import setup_logging

logger = logging.getLogger(__name__)

CONFIG_FILE = "/opt/weekly-report/config.yaml"
OUTPUT_DIR = "/opt/weekly-report/data"


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    return inject_secrets(config)


def calculate_period() -> tuple[str, str]:
    """
    Calcula periodo: sexta-feira da semana passada ate quinta-feira da semana atual.
    Comportamento fixo independente do dia que rodar.
    """
    today = datetime.now().date()
    # weekday(): 0=seg, 1=ter, 2=qua, 3=qui, 4=sex, 5=sab, 6=dom
    days_since_thursday = (today.weekday() - 3) % 7
    if days_since_thursday == 0 and datetime.now().hour < 23:
        days_since_thursday = 7
    last_thursday = today - timedelta(days=days_since_thursday)
    last_friday = last_thursday - timedelta(days=6)
    return last_friday.strftime("%Y-%m-%d"), last_thursday.strftime("%Y-%m-%d")


def collect_otrs(config: dict, start_date: str, end_date: str) -> list[dict]:
    from collectors.otrs_collector import OTRSCollector
    logger.info("Coletando chamados OTRS (%s a %s)...", start_date, end_date)
    collector = OTRSCollector(config["otrs"])
    queues, _ = collector.collect(start_date, end_date)
    for q in queues:
        logger.info("  %s: abertos=%d, fechados=%d, backlog=%d",
                    q["queue_name"], q["opened"], q["closed"], q["backlog"])
    return queues


def collect_aws_costs(config: dict, start_date: str, end_date: str) -> dict:
    import boto3
    logger.info("Coletando custos AWS (%s a %s)...", start_date, end_date)
    client = boto3.client("ce", region_name="us-east-1")

    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    end_exclusive = end_dt.strftime("%Y-%m-%d")

    total_resp = client.get_cost_and_usage(
        TimePeriod={"Start": start_date, "End": end_exclusive},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
    )
    total_cost = 0.0
    currency = "USD"
    for result in total_resp.get("ResultsByTime", []):
        total_cost += float(result["Total"]["UnblendedCost"]["Amount"])
        currency = result["Total"]["UnblendedCost"]["Unit"]

    # Breakdown por conta
    account_resp = client.get_cost_and_usage(
        TimePeriod={"Start": start_date, "End": end_exclusive},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
    )
    account_totals = {}
    for result in account_resp.get("ResultsByTime", []):
        for group in result.get("Groups", []):
            aid = group["Keys"][0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            account_totals[aid] = account_totals.get(aid, 0.0) + amount

    accounts = [
        {"account_id": aid, "cost": round(cost, 2)}
        for aid, cost in account_totals.items() if cost > 0.01
    ]

    try:
        org_client = boto3.client("organizations")
        for acc in accounts:
            try:
                info = org_client.describe_account(AccountId=acc["account_id"])
                acc["account_name"] = info["Account"]["Name"]
            except Exception:
                acc["account_name"] = acc["account_id"]
    except Exception:
        for acc in accounts:
            acc["account_name"] = acc["account_id"]

    accounts.sort(key=lambda x: x["cost"], reverse=True)

    # Breakdown por servico
    service_resp = client.get_cost_and_usage(
        TimePeriod={"Start": start_date, "End": end_exclusive},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    service_totals = {}
    for result in service_resp.get("ResultsByTime", []):
        for group in result.get("Groups", []):
            name = group["Keys"][0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            service_totals[name] = service_totals.get(name, 0.0) + amount

    services = [
        {"service": name, "cost": round(cost, 2)}
        for name, cost in service_totals.items() if cost > 0.01
    ]
    services.sort(key=lambda x: x["cost"], reverse=True)

    logger.info("  AWS Total: %s %.2f", currency, total_cost)
    return {
        "provider": "AWS",
        "period": {"start": start_date, "end": end_date},
        "currency": currency,
        "total_cost": round(total_cost, 2),
        "accounts": accounts,
        "top_services": services[:10],
    }


def collect_oci_costs(config: dict, start_date: str, end_date: str) -> dict:
    import oci
    logger.info("Coletando custos OCI (%s a %s)...", start_date, end_date)
    tenant_id = config["oci"]["tenant_id"]
    oci_config = oci.config.from_file()
    usage_client = oci.usage_api.UsageapiClient(oci_config)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    total_request = oci.usage_api.models.RequestSummarizedUsagesDetails(
        tenant_id=tenant_id,
        time_usage_started=start_dt,
        time_usage_ended=end_dt,
        granularity="DAILY",
        query_type="COST",
    )
    total_resp = usage_client.request_summarized_usages(total_request)
    total_cost = 0.0
    currency = "USD"
    for item in total_resp.data.items:
        if item.computed_amount is not None:
            total_cost += item.computed_amount
            currency = item.currency or currency

    service_request = oci.usage_api.models.RequestSummarizedUsagesDetails(
        tenant_id=tenant_id,
        time_usage_started=start_dt,
        time_usage_ended=end_dt,
        granularity="DAILY",
        query_type="COST",
        group_by=["service"],
    )
    service_resp = usage_client.request_summarized_usages(service_request)
    service_totals = {}
    for item in service_resp.data.items:
        if item.computed_amount and item.computed_amount > 0.01:
            name = item.service or "Unknown"
            service_totals[name] = service_totals.get(name, 0.0) + item.computed_amount

    services = [
        {"service": name, "cost": round(cost, 2)}
        for name, cost in service_totals.items()
    ]
    services.sort(key=lambda x: x["cost"], reverse=True)

    logger.info("  OCI Total: %s %.2f", currency, total_cost)
    return {
        "provider": "OCI",
        "period": {"start": start_date, "end": end_date},
        "currency": currency,
        "total_cost": round(total_cost, 2),
        "top_services": services[:10],
    }


def collect_golden_cloud(config: dict) -> dict:
    from collectors.golden_collector import GoldenCloudCollector
    logger.info("Coletando custos Golden Cloud...")
    collector = GoldenCloudCollector(config["golden_cloud"])
    data = collector.collect()
    logger.info("  Golden Cloud Total: %s %.2f", data["currency"], data["total_cost"])
    return data


def get_dollar_rate() -> float:
    import requests
    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest?from=USD&to=BRL",
            timeout=10,
        )
        data = resp.json()
        return data["rates"]["BRL"]
    except Exception:
        pass

    today = datetime.now()
    for i in range(5):
        date = (today - timedelta(days=i)).strftime("%m-%d-%Y")
        url = (
            f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            f"CotacaoDolarDia(dataCotacao=@dataCotacao)"
            f"?@dataCotacao='{date}'&$format=json"
        )
        try:
            import requests as req
            resp = req.get(url, timeout=10)
            data = resp.json()
            if data.get("value"):
                return data["value"][-1]["cotacaoVenda"]
        except Exception:
            continue

    logger.error("Sem cotacao disponivel, usando fallback 5.25")
    return 5.25


def send_email_with_attachment(config: dict, subject: str, html_body: str,
                                pdf_path: str, to_addrs: list[str] = None):
    import base64
    import msal
    import urllib.request

    email_cfg = config["email"]
    tenant_id = email_cfg["tenant_id"]
    client_id = email_cfg["client_id"]
    client_secret = email_cfg["client_secret"]
    user_principal_name = email_cfg["user_principal_name"]
    recipients = to_addrs or email_cfg["to"]

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(f"Falha ao obter token: {result.get('error_description', result)}")
    token = result["access_token"]

    with open(pdf_path, "rb") as f:
        pdf_content = base64.b64encode(f.read()).decode("utf-8")

    pdf_filename = os.path.basename(pdf_path)

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body,
            },
            "toRecipients": [
                {"emailAddress": {"address": addr}} for addr in recipients
            ],
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": pdf_filename,
                    "contentType": "application/pdf",
                    "contentBytes": pdf_content,
                }
            ],
        },
        "saveToSentItems": "true",
    }

    url = f"https://graph.microsoft.com/v1.0/users/{user_principal_name}/sendMail"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        urllib.request.urlopen(req)
        logger.info("E-mail enviado para %s com PDF anexado", ", ".join(recipients))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Graph API erro {e.code}: {body}")


def build_email_body(report_data: dict) -> str:
    period = report_data.get("period", {})
    start = period.get("start", "")
    end = period.get("end", "")

    try:
        dt_start = datetime.strptime(start, "%Y-%m-%d")
        dt_end = datetime.strptime(end, "%Y-%m-%d")
        period_str = f"{dt_start.strftime('%d/%m/%Y')} a {dt_end.strftime('%d/%m/%Y')}"
    except ValueError:
        period_str = f"{start} a {end}"

    total_brl = report_data.get("total_cloud_cost_brl", 0)
    total_opened = sum(q.get("opened", 0) for q in report_data.get("otrs_queues", []))
    total_closed = sum(q.get("closed", 0) for q in report_data.get("otrs_queues", []))

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #2c3e50; max-width: 600px;">
        <div style="background-color: #1a5276; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">Relatorio Semanal</h1>
            <p style="color: #bdc3c7; margin: 5px 0;">{period_str}</p>
        </div>
        <div style="padding: 20px;">
            <p>Segue em anexo o relatorio semanal de TI e Cloud referente ao periodo
               de <strong>{start}</strong> a <strong>{end}</strong>.</p>

            <h3 style="color: #1a5276;">Resumo</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #eaf2f8;">
                    <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Custo Total Cloud</strong></td>
                    <td style="padding: 8px; border: 1px solid #bdc3c7; text-align: right;">R$ {total_brl:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Chamados Abertos</strong></td>
                    <td style="padding: 8px; border: 1px solid #bdc3c7; text-align: right;">{total_opened}</td>
                </tr>
                <tr style="background-color: #eaf2f8;">
                    <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Chamados Fechados</strong></td>
                    <td style="padding: 8px; border: 1px solid #bdc3c7; text-align: right;">{total_closed}</td>
                </tr>
            </table>

            <p style="margin-top: 20px; color: #7f8c8d; font-size: 12px;">
                O relatorio completo esta no PDF anexado.<br>
                Gerado automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M')}.
            </p>
        </div>
    </body>
    </html>
    """
    return html


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="Relatorio Semanal PDF - Surf Telecom")
    parser.add_argument("--start", help="Data inicio (YYYY-MM-DD). Default: sexta passada")
    parser.add_argument("--end", help="Data fim (YYYY-MM-DD). Default: quinta atual")
    parser.add_argument("--dry-run", action="store_true", help="Gera PDF mas nao envia e-mail")
    parser.add_argument("--to", action="append", help="Destinatarios (pode repetir). Default: config.yaml")
    parser.add_argument("--skip-otrs", action="store_true", help="Pula coleta OTRS")
    parser.add_argument("--skip-aws", action="store_true", help="Pula coleta AWS")
    parser.add_argument("--skip-oci", action="store_true", help="Pula coleta OCI")
    parser.add_argument("--skip-golden", action="store_true", help="Pula coleta Golden Cloud")
    parser.add_argument("--output", help="Caminho do PDF de saida (default: auto)")
    args = parser.parse_args()

    config = load_config()
    failures = []

    # Periodo: sexta a quinta (automatico ou manual)
    if args.start and args.end:
        start_date, end_date = args.start, args.end
    else:
        start_date, end_date = calculate_period()

    logger.info("=== Relatorio Semanal PDF - Surf Telecom ===")
    logger.info("Periodo: %s a %s", start_date, end_date)

    # Nome do arquivo
    try:
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")
        pdf_filename = f"Relatorio_Semanal_{dt_start.strftime('%d%m%Y')}_{dt_end.strftime('%d%m%Y')}.pdf"
    except ValueError:
        pdf_filename = f"Relatorio_Semanal_{start_date}_{end_date}.pdf"

    # 1. Coleta OTRS
    otrs_queues = []
    if not args.skip_otrs:
        try:
            otrs_queues = collect_otrs(config, start_date, end_date)
        except Exception as e:
            logger.error("OTRS ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"OTRS: {e}")
    else:
        logger.info("Pulando OTRS (--skip-otrs)")

    # 2. Coleta custos
    cloud_costs = []

    # AWS
    if not args.skip_aws and config.get("aws", {}).get("enabled"):
        try:
            aws_data = collect_aws_costs(config, start_date, end_date)
            cloud_costs.append(aws_data)
        except Exception as e:
            logger.error("AWS ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"AWS: {e}")
    else:
        logger.info("Pulando AWS")

    # OCI
    if not args.skip_oci and config.get("oci", {}).get("enabled"):
        try:
            oci_data = collect_oci_costs(config, start_date, end_date)
            cloud_costs.append(oci_data)
        except Exception as e:
            logger.error("OCI ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"OCI: {e}")
    else:
        logger.info("Pulando OCI")

    # Golden Cloud
    if not args.skip_golden and config.get("golden_cloud", {}).get("enabled"):
        try:
            golden_data = collect_golden_cloud(config)
            cloud_costs.append(golden_data)
        except Exception as e:
            logger.error("Golden Cloud ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"Golden Cloud: {e}")
    else:
        logger.info("Pulando Golden Cloud")

    # Monday.com
    monday_boards = []
    if config.get("monday", {}).get("enabled"):
        try:
            from collectors.monday_collector import MondayCollector
            logger.info("Coletando projetos Monday.com...")
            monday = MondayCollector(config["monday"])
            monday_boards = monday.collect()
            total_items = sum(b["total_projects"] for b in monday_boards)
            logger.info("  Monday.com: %d boards, %d itens", len(monday_boards), total_items)
        except Exception as e:
            logger.error("Monday.com ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"Monday.com: {e}")

    # Microsoft Defender
    defender_data = {}
    if config.get("defender", {}).get("enabled"):
        try:
            from collectors.defender_collector import DefenderCollector
            logger.info("Coletando dados Microsoft Defender...")
            defender = DefenderCollector({
                "tenant_id": config["email"]["tenant_id"],
                "client_id": config["email"]["client_id"],
                "client_secret": config["email"]["client_secret"],
            })
            defender_data = defender.collect()
            logger.info("  Defender: %d alerts, %d devices, %d vulns",
                        len(defender_data.get("alerts", [])),
                        defender_data.get("devices", {}).get("total", 0),
                        len(defender_data.get("vulnerabilities", [])))
        except Exception as e:
            logger.error("Defender ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"Defender: {e}")

    # Cotacao e conversao
    dollar_rate = get_dollar_rate()
    logger.info("Cotacao USD/BRL: %.4f", dollar_rate)

    total_brl = 0.0
    for c in cloud_costs:
        if c.get("currency", "USD") == "USD":
            c["total_cost_brl"] = round(c["total_cost"] * dollar_rate, 2)
        else:
            c["total_cost_brl"] = c["total_cost"]
        total_brl += c["total_cost_brl"]

    # Monta report_data
    report_data = {
        "period": {"start": start_date, "end": end_date},
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "otrs_queues": otrs_queues,
        "clouds": cloud_costs,
        "total_cloud_cost_brl": round(total_brl, 2),
        "dollar_rate": dollar_rate,
        "monthly_costs": {},
        "monday_boards": monday_boards,
        "defender": defender_data,
    }

    # 3. Gera PDF
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = args.output or os.path.join(OUTPUT_DIR, pdf_filename)

    from report.pdf_generator import WeeklyPDFGenerator
    generator = WeeklyPDFGenerator(pdf_path)
    generator.generate(report_data)
    logger.info("PDF gerado: %s", pdf_path)

    if failures:
        logger.warning("Falhas na coleta: %s", "; ".join(failures))

    # 4. Envia e-mail
    if args.dry_run:
        logger.info("DRY-RUN: PDF gerado em %s mas e-mail nao enviado.", pdf_path)
        return

    try:
        subject = f"Relatorio Semanal TI e Cloud - {start_date} a {end_date}"
        html_body = build_email_body(report_data)
        send_email_with_attachment(config, subject, html_body, pdf_path, args.to)
    except Exception as e:
        logger.error("EMAIL ERRO: %s", e)
        logger.exception("Detalhes:")
        sys.exit(1)

    logger.info("=== Concluido ===")


if __name__ == "__main__":
    main()
