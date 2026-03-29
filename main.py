#!/usr/bin/env python3
"""
Orquestrador do Relatório Semanal.
Coleta dados, gera dashboard e envia por e-mail e Teams.

Uso:
    python main.py              # Execução normal (período automático: sexta a quinta)
    python main.py --dry-run    # Gera dashboard mas não envia e-mail/Teams
    python main.py --start 2026-03-06 --end 2026-03-12  # Período manual
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta

import yaml

from env_loader import inject_secrets
from log_config import setup_logging

logger = logging.getLogger(__name__)

CONFIG_FILE = "/opt/weekly-report/config.yaml"


def _notify_failure(config: dict, failures: list[str]):
    """Envia alerta de falha no Teams se houver erros de coleta."""
    if not failures:
        return
    webhook_url = config.get("teams", {}).get("webhook_url", "")
    if not webhook_url:
        return
    try:
        import requests as req
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "⚠️ Relatório Semanal — Falhas na Coleta",
                    "weight": "Bolder",
                    "size": "Medium",
                    "color": "Attention",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": "\n".join(f"- {f}" for f in failures),
                    "wrap": True,
                },
            ],
        }
        req.post(webhook_url, json=card, timeout=15)
        logger.info("Alerta de falhas enviado ao Teams")
    except Exception as e:
        logger.error(f"Erro ao enviar alerta de falhas: {e}")
OTRS_CACHE_FILE = "/opt/weekly-report/data/otrs_cache.json"


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    return inject_secrets(config)


def calculate_period() -> tuple[str, str]:
    """
    Calcula o período do relatório: sexta-feira a quinta-feira.

    Ciclo semanal da empresa:
      - Período: sexta a quinta (ex: 06/03 a 12/03, 13/03 a 19/03)
      - Reunião: segunda-feira (apresenta resultados da semana anterior)
      - Relatório completo: gerado na sexta (período encerrou na quinta)

    Lógica: encontra a última quinta-feira que já passou e recua 6 dias
    até a sexta anterior.
    """
    today = datetime.now().date()
    # weekday(): 0=seg, 1=ter, 2=qua, 3=qui, 4=sex, 5=sab, 6=dom
    days_since_thursday = (today.weekday() - 3) % 7
    if days_since_thursday == 0 and datetime.now().hour < 23:
        # Se é quinta mas ainda não acabou o dia, pega a quinta anterior
        days_since_thursday = 7
    last_thursday = today - timedelta(days=days_since_thursday)
    last_friday = last_thursday - timedelta(days=6)

    return last_friday.strftime("%Y-%m-%d"), last_thursday.strftime("%Y-%m-%d")


def _load_otrs_cache(fallback: list) -> list:
    """Carrega últimos dados reais do OTRS do cache local."""
    if os.path.exists(OTRS_CACHE_FILE):
        try:
            with open(OTRS_CACHE_FILE) as f:
                data = json.load(f)
            if data:
                logger.info("Cache carregado (%d filas)", len(data))
                return data
        except Exception:
            pass
    logger.info("Sem cache disponível, usando dados zerados")
    return fallback


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="Relatório Semanal - Surf Telecom - Fila CLOUD")
    parser.add_argument("--dry-run", action="store_true", help="Gera sem enviar")
    parser.add_argument("--refresh", action="store_true",
                        help="Atualiza apenas custos no dashboard (sem histórico, sem envio)")
    parser.add_argument("--start", help="Data início (YYYY-MM-DD)")
    parser.add_argument("--end", help="Data fim (YYYY-MM-DD)")
    parser.add_argument("--skip-otrs", action="store_true", help="Pula coleta OTRS")
    parser.add_argument("--skip-aws", action="store_true", help="Pula coleta AWS")
    parser.add_argument("--skip-oci", action="store_true", help="Pula coleta OCI")
    args = parser.parse_args()

    config = load_config()
    failures = []

    # --refresh implica --dry-run (sem envio, sem salvar histórico)
    if args.refresh:
        args.dry_run = True

    # Período
    if args.start and args.end:
        start_date, end_date = args.start, args.end
    else:
        start_date, end_date = calculate_period()

    logger.info("=== Relatório Semanal - Surf Telecom ===")
    logger.info("Período: %s a %s", start_date, end_date)
    logger.info("Gerado em: %s", datetime.now().strftime('%d/%m/%Y %H:%M'))

    # 1. Coleta OTRS (múltiplas filas)
    def _empty_queue(name):
        return {
            "queue_name": name,
            "period": {"start": start_date, "end": end_date},
            "opened": 0, "closed": 0, "backlog": 0,
            "avg_first_response_hours": None, "avg_resolution_hours": None,
            "sla_first_response_met": None, "sla_resolution_met": None,
            "first_response_target": 24, "resolution_target": 72,
            "tickets": [],
        }

    configured_queues = config.get("otrs", {}).get("queues", [{"name": "CLOUD"}])
    otrs_queues = [_empty_queue(q["name"]) for q in configured_queues]

    # Calcula data D-1 (ontem) para métricas diárias
    yesterday = (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
    otrs_daily_queues = []

    if not args.skip_otrs:
        try:
            from collectors.otrs_collector import OTRSCollector
            logger.info("Coletando chamados...")
            collector = OTRSCollector(config["otrs"])
            otrs_queues, otrs_daily_queues = collector.collect(start_date, end_date, daily_end_date=yesterday)
            # Salva cache dos dados reais
            with open(OTRS_CACHE_FILE, "w") as f:
                json.dump(otrs_queues, f, indent=2)
            logger.info("Cache salvo")
        except Exception as e:
            logger.error("OTRS ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"OTRS: {e}")
            logger.info("Tentando usar cache...")
            otrs_queues = _load_otrs_cache(otrs_queues)
    else:
        logger.info("Pulando OTRS (--skip-otrs), usando cache...")
        otrs_queues = _load_otrs_cache(otrs_queues)

    # Compatibilidade: otrs_data aponta para a primeira fila
    otrs_data = otrs_queues[0] if otrs_queues else _empty_queue("CLOUD")

    # 2. Coleta custos
    cloud_costs = []

    # AWS
    if not args.skip_aws and config.get("aws", {}).get("enabled"):
        try:
            from collectors.aws_collector import AWSCollector
            logger.info("Coletando custos AWS...")
            aws = AWSCollector(config["aws"])
            aws_data = aws.collect()
            cloud_costs.append(aws_data)
            logger.info("AWS Total: %s %.2f", aws_data['currency'], aws_data['total_cost'])
        except Exception as e:
            logger.error("AWS ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"AWS: {e}")
    else:
        logger.info("Pulando AWS")

    # OCI
    if not args.skip_oci and config.get("oci", {}).get("enabled"):
        try:
            from collectors.oci_collector import OCICollector
            logger.info("Coletando custos OCI...")
            oci_coll = OCICollector(config["oci"])
            oci_data = oci_coll.collect()
            cloud_costs.append(oci_data)
            logger.info("OCI Total: %s %.2f", oci_data['currency'], oci_data['total_cost'])
        except Exception as e:
            logger.error("OCI ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"OCI: {e}")
    else:
        logger.info("Pulando OCI")

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

    # Golden Cloud
    if config.get("golden_cloud", {}).get("enabled"):
        try:
            from collectors.golden_collector import GoldenCloudCollector
            logger.info("Coletando custos Golden Cloud...")
            golden = GoldenCloudCollector(config["golden_cloud"])
            golden_data = golden.collect()
            cloud_costs.append(golden_data)
            logger.info("Golden Cloud Total: %s %.2f (%s)",
                        golden_data['currency'], golden_data['total_cost'],
                        golden_data.get('status', ''))
        except Exception as e:
            logger.error("Golden Cloud ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"Golden Cloud: {e}")

    # Histórico mensal (últimos 3 meses completos)
    monthly_costs = {}

    # AWS mensal
    if not args.skip_aws and config.get("aws", {}).get("enabled"):
        try:
            monthly_costs["AWS"] = aws.collect_monthly(3)
            logger.info("AWS histórico mensal: %s", monthly_costs["AWS"])
        except Exception as e:
            logger.error("Erro ao coletar histórico AWS: %s", e)

    # OCI mensal
    if not args.skip_oci and config.get("oci", {}).get("enabled"):
        try:
            monthly_costs["OCI"] = oci_coll.collect_monthly(3)
            logger.info("OCI histórico mensal: %s", monthly_costs["OCI"])
        except Exception as e:
            logger.error("Erro ao coletar histórico OCI: %s", e)

    # Golden Cloud mensal (já vem do cache/scraping - usa details do collect)
    for c in cloud_costs:
        if c.get("provider") == "Golden Cloud" and c.get("details"):
            monthly_costs["Golden Cloud"] = [
                {"month": d.get("month", ""), "cost": d.get("cost", 0), "currency": "BRL"}
                for d in c["details"][-3:]  # últimos 3
            ]

    # Monday.com
    monday_boards = []
    if config.get("monday", {}).get("enabled"):
        try:
            from collectors.monday_collector import MondayCollector
            logger.info("Coletando projetos Monday.com...")
            monday = MondayCollector(config["monday"])
            monday_boards = monday.collect()
            total_items = sum(b["total_projects"] for b in monday_boards)
            logger.info("Monday.com: %d boards, %d itens", len(monday_boards), total_items)
        except Exception as e:
            logger.error("Monday.com ERRO: %s", e)
            logger.exception("Detalhes:")
            failures.append(f"Monday.com: {e}")

    # 3. Gera relatório
    try:
        from report.generator import ReportGenerator
        logger.info("Gerando dashboard e e-mail...")
        generator = ReportGenerator(config)
        # TODO: aba "Diário (D-1)" desabilitada temporariamente
        result = generator.generate(otrs_data, cloud_costs, monday_boards=monday_boards, otrs_queues=otrs_queues, otrs_daily_queues=[], save_history=not args.refresh, monthly_costs=monthly_costs, finops_data=finops_data)
        logger.info("Dashboard: %s", result['dashboard_path'])
        # Salva JSON para o frontend React
        report_json_path = "/opt/weekly-report/data/report-data.json"
        generator.save_report_json(result["report_data"], report_json_path)
        logger.info("Report JSON: %s", report_json_path)
    except Exception as e:
        logger.error("REPORT ERRO: %s", e)
        logger.exception("Detalhes:")
        sys.exit(1)

    _notify_failure(config, failures)

    # 4. Envia
    if args.dry_run:
        logger.info("DRY-RUN: Relatório gerado mas não enviado.")
        return

    # E-mail
    try:
        from delivery.email_sender import EmailSender
        period_str = f"{start_date} a {end_date}"
        sender = EmailSender(config["email"])
        sender.send(
            subject=f"Relatório Semanal - Surf Telecom — {period_str}",
            html_body=result["email_html"],
        )
    except Exception as e:
        logger.error("EMAIL ERRO: %s", e)
        logger.exception("Detalhes:")

    # Teams
    try:
        from delivery.teams_sender import TeamsSender
        teams = TeamsSender(config["teams"])
        teams.send(result["report_data"], config["dashboard"]["base_url"])
    except Exception as e:
        logger.error("TEAMS ERRO: %s", e)
        logger.exception("Detalhes:")

    logger.info("=== Concluído ===")


if __name__ == "__main__":
    main()
