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
import os
import sys
import traceback
from datetime import datetime, timedelta

import yaml

from env_loader import inject_secrets

CONFIG_FILE = "/opt/weekly-report/config.yaml"
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
                print(f"[OTRS] Cache carregado ({len(data)} filas)")
                return data
        except Exception:
            pass
    print("[OTRS] Sem cache disponível, usando dados zerados")
    return fallback


def main():
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

    # --refresh implica --dry-run (sem envio, sem salvar histórico)
    if args.refresh:
        args.dry_run = True

    # Período
    if args.start and args.end:
        start_date, end_date = args.start, args.end
    else:
        start_date, end_date = calculate_period()

    print(f"=== Relatório Semanal - Surf Telecom ===")
    print(f"Período: {start_date} a {end_date}")
    print(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print()

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
            print("[OTRS] Coletando chamados...")
            collector = OTRSCollector(config["otrs"])
            otrs_queues, otrs_daily_queues = collector.collect(start_date, end_date, daily_end_date=yesterday)
            # Salva cache dos dados reais
            with open(OTRS_CACHE_FILE, "w") as f:
                json.dump(otrs_queues, f, indent=2)
            print("[OTRS] Cache salvo")
        except Exception as e:
            print(f"[OTRS] ERRO: {e}")
            traceback.print_exc()
            print("[OTRS] Tentando usar cache...")
            otrs_queues = _load_otrs_cache(otrs_queues)
    else:
        print("[OTRS] Pulando (--skip-otrs), usando cache...")
        otrs_queues = _load_otrs_cache(otrs_queues)

    # Compatibilidade: otrs_data aponta para a primeira fila
    otrs_data = otrs_queues[0] if otrs_queues else empty_queue

    # 2. Coleta custos
    cloud_costs = []

    # AWS
    if not args.skip_aws and config.get("aws", {}).get("enabled"):
        try:
            from collectors.aws_collector import AWSCollector
            print("[AWS] Coletando custos...")
            aws = AWSCollector(config["aws"])
            aws_data = aws.collect()
            cloud_costs.append(aws_data)
            print(f"[AWS] Total: {aws_data['currency']} {aws_data['total_cost']:,.2f}")
        except Exception as e:
            print(f"[AWS] ERRO: {e}")
            traceback.print_exc()
    else:
        print("[AWS] Pulando")

    # OCI
    if not args.skip_oci and config.get("oci", {}).get("enabled"):
        try:
            from collectors.oci_collector import OCICollector
            print("[OCI] Coletando custos...")
            oci_coll = OCICollector(config["oci"])
            oci_data = oci_coll.collect()
            cloud_costs.append(oci_data)
            print(f"[OCI] Total: {oci_data['currency']} {oci_data['total_cost']:,.2f}")
        except Exception as e:
            print(f"[OCI] ERRO: {e}")
            traceback.print_exc()
    else:
        print("[OCI] Pulando")

    # Golden Cloud
    if config.get("golden_cloud", {}).get("enabled"):
        try:
            from collectors.golden_collector import GoldenCloudCollector
            print("[GOLDEN] Coletando custos...")
            golden = GoldenCloudCollector(config["golden_cloud"])
            golden_data = golden.collect()
            cloud_costs.append(golden_data)
            print(f"[GOLDEN] Total: {golden_data['currency']} "
                  f"{golden_data['total_cost']:,.2f} "
                  f"({golden_data.get('status', '')})")
        except Exception as e:
            print(f"[GOLDEN] ERRO: {e}")
            traceback.print_exc()

    # Monday.com
    monday_boards = []
    if config.get("monday", {}).get("enabled"):
        try:
            from collectors.monday_collector import MondayCollector
            print("[MONDAY] Coletando projetos...")
            monday = MondayCollector(config["monday"])
            monday_boards = monday.collect()
            total_items = sum(b["total_projects"] for b in monday_boards)
            print(f"[MONDAY] {len(monday_boards)} boards, {total_items} itens")
        except Exception as e:
            print(f"[MONDAY] ERRO: {e}")
            traceback.print_exc()

    # 3. Gera relatório
    print()
    try:
        from report.generator import ReportGenerator
        print("[REPORT] Gerando dashboard e e-mail...")
        generator = ReportGenerator(config)
        # TODO: aba "Diário (D-1)" desabilitada temporariamente
        result = generator.generate(otrs_data, cloud_costs, monday_boards=monday_boards, otrs_queues=otrs_queues, otrs_daily_queues=[], save_history=not args.refresh)
        print(f"[REPORT] Dashboard: {result['dashboard_path']}")
    except Exception as e:
        print(f"[REPORT] ERRO: {e}")
        traceback.print_exc()
        sys.exit(1)

    # 4. Envia
    if args.dry_run:
        print("\n[DRY-RUN] Relatório gerado mas não enviado.")
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
        print(f"[EMAIL] ERRO: {e}")
        traceback.print_exc()

    # Teams
    try:
        from delivery.teams_sender import TeamsSender
        teams = TeamsSender(config["teams"])
        teams.send(result["report_data"], config["dashboard"]["base_url"])
    except Exception as e:
        print(f"[TEAMS] ERRO: {e}")
        traceback.print_exc()

    print("\n=== Concluído ===")


if __name__ == "__main__":
    main()
