#!/usr/bin/env python3
"""
Alerta de prazos no Teams — envia notificação 15 dias antes do vencimento.
Roda diariamente via cron.

Uso:
    python scripts/deadline_alert.py              # Envia alertas
    python scripts/deadline_alert.py --dry-run    # Mostra sem enviar
    python scripts/deadline_alert.py --days 30    # Altera janela de alerta
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

import requests
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from env_loader import inject_secrets
from log_config import setup_logging
from collectors.monday_collector import MondayCollector

logger = logging.getLogger(__name__)

DONE_STATUSES = {"Feito", "Concluído", "Concluido", "Done"}

CONFIG_FILE = "/opt/weekly-report/config.yaml"


def load_config():
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    inject_secrets(config)
    return config


def collect_alerts(boards: list, days: int) -> list[dict]:
    """Retorna itens cujo prazo efetivo vence dentro de `days` dias."""
    today = datetime.now().date()
    limit = today + timedelta(days=days)
    alerts = []

    for board in boards:
        items = board.get("filtered_subitems") or board.get("projects") or []
        for item in items:
            status = item.get("status", "")
            if status in DONE_STATUSES:
                continue

            # Prazo efetivo: nova previsão tem prioridade
            deadline_str = item.get("new_due_date") or item.get("due_date") or ""
            if not deadline_str:
                continue

            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            if deadline > limit:
                continue

            days_left = (deadline - today).days
            alerts.append({
                "board": board.get("board_name", ""),
                "category": board.get("category", ""),
                "name": item.get("name", ""),
                "group": item.get("parent_name") or item.get("group", ""),
                "person": item.get("person", ""),
                "status": status,
                "deadline": deadline_str,
                "days_left": days_left,
            })

    # Ordena: mais urgentes primeiro
    alerts.sort(key=lambda a: a["days_left"])
    return alerts


def send_teams_alert(webhook_url: str, alerts: list[dict], days: int, dashboard_url: str):
    """Envia Adaptive Card com alertas de prazo para o Teams."""

    # Agrupa por urgência
    overdue = [a for a in alerts if a["days_left"] < 0]
    expiring_soon = [a for a in alerts if 0 <= a["days_left"] <= 7]
    expiring_later = [a for a in alerts if 7 < a["days_left"] <= days]

    def make_rows(items: list[dict]) -> list[dict]:
        rows = []
        for a in items:
            if a["days_left"] < 0:
                prazo_text = f"**VENCIDO** ({abs(a['days_left'])}d atrás)"
            elif a["days_left"] == 0:
                prazo_text = "**VENCE HOJE**"
            else:
                prazo_text = f"{a['days_left']}d restantes"

            rows.append({
                "type": "TableRow",
                "cells": [
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["name"], "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["board"], "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["person"] or "—", "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["deadline"], "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": prazo_text, "wrap": True}]},
                ],
            })
        return rows

    body = [
        {
            "type": "Container",
            "style": "attention",
            "bleed": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": f"⏰ Alerta de Prazos — {len(alerts)} ite{'m' if len(alerts) == 1 else 'ns'} nos próximos {days} dias",
                    "weight": "Bolder",
                    "size": "Medium",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    "spacing": "None",
                    "isSubtle": True,
                    "wrap": True,
                },
            ],
        },
    ]

    header_row = {
        "type": "TableRow",
        "style": "accent",
        "cells": [
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Item", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Board", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Responsável", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Prazo", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Situação", "weight": "Bolder", "wrap": True}]},
        ],
    }

    if overdue:
        body.append({
            "type": "TextBlock",
            "text": f"🔴 Vencidos ({len(overdue)})",
            "weight": "Bolder",
            "color": "Attention",
            "spacing": "Large",
            "wrap": True,
        })
        body.append({
            "type": "Table",
            "gridStyle": "accent",
            "firstRowAsHeader": True,
            "showGridLines": True,
            "columns": [{"width": 3}, {"width": 2}, {"width": 2}, {"width": 1}, {"width": 2}],
            "rows": [header_row] + make_rows(overdue),
        })

    if expiring_soon:
        body.append({
            "type": "TextBlock",
            "text": f"🟡 Vencem em até 7 dias ({len(expiring_soon)})",
            "weight": "Bolder",
            "color": "Warning",
            "spacing": "Large",
            "wrap": True,
        })
        body.append({
            "type": "Table",
            "gridStyle": "accent",
            "firstRowAsHeader": True,
            "showGridLines": True,
            "columns": [{"width": 3}, {"width": 2}, {"width": 2}, {"width": 1}, {"width": 2}],
            "rows": [header_row] + make_rows(expiring_soon),
        })

    if expiring_later:
        body.append({
            "type": "TextBlock",
            "text": f"🟢 Vencem em 8–{days} dias ({len(expiring_later)})",
            "weight": "Bolder",
            "color": "Good",
            "spacing": "Large",
            "wrap": True,
        })
        body.append({
            "type": "Table",
            "gridStyle": "accent",
            "firstRowAsHeader": True,
            "showGridLines": True,
            "columns": [{"width": 3}, {"width": 2}, {"width": 2}, {"width": 1}, {"width": 2}],
            "rows": [header_row] + make_rows(expiring_later),
        })

    payload = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "📈 Abrir Dashboard",
                "url": dashboard_url,
                "style": "positive",
            }
        ],
    }

    resp = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    if resp.status_code in (200, 202):
        logger.info("Alerta enviado com sucesso ao Teams")
    else:
        logger.error("Erro ao enviar alerta: %s - %s", resp.status_code, resp.text)


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Alerta de prazos via Teams")
    parser.add_argument("--dry-run", action="store_true", help="Mostra alertas sem enviar")
    parser.add_argument("--days", type=int, default=15, help="Janela de alerta em dias (default: 15)")
    args = parser.parse_args()

    config = load_config()

    logger.info("Coletando projetos Monday.com...")
    monday = MondayCollector(config["monday"])
    boards = monday.collect()
    total_items = sum(b["total_projects"] for b in boards)
    logger.info("Monday.com: %d boards, %d itens", len(boards), total_items)

    alerts = collect_alerts(boards, args.days)

    if not alerts:
        logger.info("Nenhum item com prazo nos próximos %d dias.", args.days)
        return

    logger.info("Encontrados %d itens com prazo nos próximos %d dias:", len(alerts), args.days)
    for a in alerts:
        tag = "VENCIDO" if a["days_left"] < 0 else f"{a['days_left']}d"
        logger.info("  [%s] %s — %s (%s)", tag, a["name"], a["deadline"], a["board"])

    if args.dry_run:
        logger.info("DRY-RUN: Alerta não enviado.")
        return

    webhook_url = config.get("teams", {}).get("webhook_url", "")
    if not webhook_url:
        logger.error("TEAMS_WEBHOOK_URL não configurado")
        return

    dashboard_url = config.get("dashboard", {}).get("base_url", "")
    send_teams_alert(webhook_url, alerts, args.days, dashboard_url)


if __name__ == "__main__":
    main()
