#!/usr/bin/env python3
"""
Relatório de projetos de segurança — envia Adaptive Card no Teams
com status dos boards de segurança do Monday.com.

Modos:
  - report:  Relatório completo com status de todos os projetos
  - alertas: Alerta de tarefas vencendo em 5, 3 ou 1 dia

Canal: Segurança da Informação > Dashboard Segurança

Uso:
    python scripts/security_report.py                    # Envia relatório
    python scripts/security_report.py alertas            # Envia alertas de prazo
    python scripts/security_report.py --dry-run          # Relatório sem enviar
    python scripts/security_report.py alertas --dry-run  # Alertas sem enviar
"""

import argparse
import logging
import os
import sys
from datetime import datetime

import requests
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from env_loader import inject_secrets
from log_config import setup_logging
from collectors.monday_collector import MondayCollector

logger = logging.getLogger(__name__)

CONFIG_FILE = "/opt/weekly-report/config.yaml"
WEBHOOK_URL = (
    "https://defaultb0f914e457bd42ea8f5d64e0d88a0d.1b.environment.api.powerplatform.com:443"
    "/powerautomate/automations/direct/workflows/fbf23b928a454b07bf2db3d47ff4ecdd"
    "/triggers/manual/paths/invoke?api-version=1"
    "&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0"
    "&sig=droqE8bgrYv1WmP2Pknn4Y9T8KfLfZ_uupOz9yYVo-8"
)

DONE_STATUSES = {"Feito", "Concluído", "Concluido", "Done"}
ALERT_DAYS = [5, 3, 1]


def load_config():
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    inject_secrets(config)
    return config


def send_card(card: dict):
    """Envia Adaptive Card para o webhook do Teams."""
    resp = requests.post(
        WEBHOOK_URL,
        json=card,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code in (200, 202):
        logger.info("Card enviado ao Teams (Segurança da Informação > Dashboard Segurança)")
    else:
        logger.error("Erro ao enviar: %s - %s", resp.status_code, resp.text)


# ==================== RELATÓRIO ====================

def build_report_card(sec_boards: list[dict], dashboard_url: str) -> dict:
    """Monta Adaptive Card com status dos projetos de segurança."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    body = [
        {
            "type": "Container",
            "style": "emphasis",
            "bleed": True,
            "items": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [{"type": "TextBlock", "text": "🔒", "size": "Large"}],
                            "verticalContentAlignment": "Center",
                        },
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {"type": "TextBlock", "text": "Relatório Segurança", "weight": "Bolder", "size": "Large", "wrap": True},
                                {"type": "TextBlock", "text": f"Projetos Monday.com — {now}", "spacing": "None", "isSubtle": True, "wrap": True},
                            ],
                        },
                    ],
                }
            ],
        },
    ]

    for board in sec_boards:
        board_name = board.get("board_name", "")
        status_summary = board.get("status_summary", {})
        total = board.get("total_projects", 0)
        done = sum(status_summary.get(s, 0) for s in DONE_STATUSES)
        pct = round(done / total * 100) if total > 0 else 0

        filter_person = board.get("filter_person", "")
        label = f"📋 {board_name}"
        if filter_person:
            label += f" (filtro: {filter_person})"

        body.append({
            "type": "TextBlock",
            "text": label,
            "weight": "Bolder",
            "color": "Accent",
            "spacing": "Large",
            "wrap": True,
        })

        # Tabela resumo
        summary_rows = [
            {
                "type": "TableRow",
                "style": "accent",
                "cells": [
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Métrica", "weight": "Bolder", "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Valor", "weight": "Bolder", "wrap": True}]},
                ],
            },
            _row("Total de Itens", str(total)),
            _row("Concluídos", f"{done} ({pct}%)"),
            _row("Pendentes", str(total - done)),
        ]

        body.append({
            "type": "Table",
            "gridStyle": "accent",
            "firstRowAsHeader": True,
            "showGridLines": True,
            "columns": [{"width": 3}, {"width": 2}],
            "rows": summary_rows,
        })

        # Tabela de status detalhado
        if status_summary:
            status_rows = [
                {
                    "type": "TableRow",
                    "style": "accent",
                    "cells": [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Status", "weight": "Bolder", "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Qtd", "weight": "Bolder", "wrap": True}]},
                    ],
                },
            ]
            for status, count in sorted(status_summary.items(), key=lambda x: -x[1]):
                icon = "✅" if status in DONE_STATUSES else "🔄"
                status_rows.append(_row(f"{icon} {status}", str(count)))

            body.append({
                "type": "Table",
                "gridStyle": "accent",
                "firstRowAsHeader": True,
                "showGridLines": True,
                "columns": [{"width": 3}, {"width": 1}],
                "rows": status_rows,
            })

        # Lista de itens pendentes
        items = board.get("filtered_subitems") or board.get("projects") or []
        pending = [i for i in items if i.get("status", "") not in DONE_STATUSES]
        if pending:
            pending_rows = [
                {
                    "type": "TableRow",
                    "style": "accent",
                    "cells": [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Item", "weight": "Bolder", "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Status", "weight": "Bolder", "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Prazo", "weight": "Bolder", "wrap": True}]},
                    ],
                },
            ]
            for item in pending:
                name = item.get("name", "")
                status = item.get("status", "Sem status")
                due = item.get("new_due_date") or item.get("due_date") or "—"
                if due != "—":
                    try:
                        due = datetime.strptime(due, "%Y-%m-%d").strftime("%d/%m/%Y")
                    except ValueError:
                        pass
                pending_rows.append({
                    "type": "TableRow",
                    "cells": [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": name, "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": status, "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": due, "wrap": True}]},
                    ],
                })

            body.append({
                "type": "TextBlock",
                "text": f"📌 Itens Pendentes ({len(pending)})",
                "weight": "Bolder",
                "spacing": "Medium",
                "wrap": True,
            })
            body.append({
                "type": "Table",
                "gridStyle": "accent",
                "firstRowAsHeader": True,
                "showGridLines": True,
                "columns": [{"width": 4}, {"width": 2}, {"width": 2}],
                "rows": pending_rows,
            })

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": [{
            "type": "Action.OpenUrl",
            "title": "📈 Abrir Dashboard",
            "url": dashboard_url,
            "style": "positive",
        }],
    }


# ==================== ALERTAS DE PRAZO ====================

def collect_deadline_alerts(sec_boards: list[dict]) -> list[dict]:
    """Retorna itens de segurança que vencem em 5, 3 ou 1 dia."""
    today = datetime.now().date()
    alerts = []

    for board in sec_boards:
        items = board.get("filtered_subitems") or board.get("projects") or []
        for item in items:
            if item.get("status", "") in DONE_STATUSES:
                continue

            new_due = item.get("new_due_date") or ""
            due = item.get("due_date") or ""
            deadline_str = new_due or due
            if not deadline_str:
                continue

            deadline_source = "Nova Prev." if new_due else "Prev. Conclusão"

            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            days_left = (deadline - today).days

            if days_left < 0:
                alerts.append({
                    "board": board.get("board_name", ""),
                    "name": item.get("name", ""),
                    "group": item.get("parent_name") or item.get("group", ""),
                    "status": item.get("status", ""),
                    "deadline": deadline_str,
                    "deadline_formatted": deadline.strftime("%d/%m/%Y"),
                    "deadline_source": deadline_source,
                    "days_left": days_left,
                })
            elif days_left in ALERT_DAYS:
                alerts.append({
                    "board": board.get("board_name", ""),
                    "name": item.get("name", ""),
                    "group": item.get("parent_name") or item.get("group", ""),
                    "status": item.get("status", ""),
                    "deadline": deadline_str,
                    "deadline_formatted": deadline.strftime("%d/%m/%Y"),
                    "deadline_source": deadline_source,
                    "days_left": days_left,
                })

    alerts.sort(key=lambda a: a["days_left"])
    return alerts


def build_alert_card(alerts: list[dict], dashboard_url: str) -> dict:
    """Monta Adaptive Card com alertas de prazo."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    overdue = [a for a in alerts if a["days_left"] < 0]
    alerts_1d = [a for a in alerts if a["days_left"] == 1]
    alerts_3d = [a for a in alerts if a["days_left"] == 3]
    alerts_5d = [a for a in alerts if a["days_left"] == 5]

    body = [
        {
            "type": "Container",
            "style": "attention",
            "bleed": True,
            "items": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [{"type": "TextBlock", "text": "🔔", "size": "Large"}],
                            "verticalContentAlignment": "Center",
                        },
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"Alerta de Prazos — Segurança ({len(alerts)} {'item' if len(alerts) == 1 else 'itens'})",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                    "wrap": True,
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"Gerado em {now}",
                                    "spacing": "None",
                                    "isSubtle": True,
                                    "wrap": True,
                                },
                            ],
                        },
                    ],
                }
            ],
        },
    ]

    header_row = {
        "type": "TableRow",
        "style": "accent",
        "cells": [
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Item", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Board", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Vencimento", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Status", "weight": "Bolder", "wrap": True}]},
        ],
    }

    def make_rows(items):
        return [{
            "type": "TableRow",
            "cells": [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["name"], "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["board"], "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["deadline_formatted"], "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["status"], "wrap": True}]},
            ],
        } for a in items]

    sections = [
        (overdue, "⚫ VENCIDO", "Attention"),
        (alerts_1d, "🔴 Vence AMANHÃ", "Attention"),
        (alerts_3d, "🟡 Vence em 3 dias", "Warning"),
        (alerts_5d, "🟢 Vence em 5 dias", "Good"),
    ]

    for items, title, color in sections:
        if not items:
            continue

        if title == "⚫ VENCIDO":
            display_items = []
            for a in items:
                days_abs = abs(a["days_left"])
                suffix = f" (atrasado {days_abs}d)"
                display_items.append({**a, "deadline_formatted": a["deadline_formatted"] + suffix})
            rows = make_rows(display_items)
        else:
            rows = make_rows(items)

        body.append({
            "type": "TextBlock",
            "text": f"{title} ({len(items)})",
            "weight": "Bolder",
            "color": color,
            "spacing": "Large",
            "wrap": True,
        })
        body.append({
            "type": "Table",
            "gridStyle": "accent",
            "firstRowAsHeader": True,
            "showGridLines": True,
            "columns": [{"width": 4}, {"width": 3}, {"width": 2}, {"width": 2}],
            "rows": [header_row] + rows,
        })

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": [{
            "type": "Action.OpenUrl",
            "title": "📈 Abrir Dashboard",
            "url": dashboard_url,
            "style": "positive",
        }],
    }


# ==================== HELPERS ====================

def _row(metric: str, value: str) -> dict:
    return {
        "type": "TableRow",
        "cells": [
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": metric, "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": value, "wrap": True}]},
        ],
    }


# ==================== MAIN ====================

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Relatório/alertas de segurança via Teams")
    parser.add_argument("modo", nargs="?", default="report", choices=["report", "alertas"],
                        help="Modo: 'report' (padrão) ou 'alertas' (prazos)")
    parser.add_argument("--dry-run", action="store_true", help="Mostra sem enviar")
    args = parser.parse_args()

    config = load_config()

    logger.info("Coletando projetos Monday.com...")
    monday = MondayCollector(config["monday"])
    boards = monday.collect()

    sec_boards = [b for b in boards if b.get("category") == "seguranca"]
    if not sec_boards:
        logger.info("Nenhum board de segurança encontrado.")
        return

    total_items = sum(b["total_projects"] for b in sec_boards)
    logger.info("Segurança: %d boards, %d itens", len(sec_boards), total_items)

    dashboard_url = config.get("dashboard", {}).get("base_url", "")

    if args.modo == "alertas":
        alerts = collect_deadline_alerts(sec_boards)
        if not alerts:
            logger.info("Nenhum item vencendo em %s dias (nem vencido).", ALERT_DAYS)
            return
        logger.info("Encontrados %d itens com alerta:", len(alerts))
        for a in alerts:
            logger.info("  [%dd] %s — %s — %s", a["days_left"], a["name"], a["deadline_formatted"], a["board"])
        card = build_alert_card(alerts, dashboard_url)
    else:
        card = build_report_card(sec_boards, dashboard_url)

    if args.dry_run:
        import json
        print(json.dumps(card, indent=2, ensure_ascii=False))
        logger.info("DRY-RUN: Card não enviado.")
        return

    send_card(card)


if __name__ == "__main__":
    main()
