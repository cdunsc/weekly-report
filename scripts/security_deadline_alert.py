#!/usr/bin/env python3
"""
Alerta de prazos de segurança — envia notificação faltando
5, 2 ou 1 dia para o vencimento das atividades.

Envia por dois canais:
  1. Adaptive Card no Teams (webhook do canal)
  2. E-mail direto para wilson.matsumoto@surf.com.br (Graph API)

Roda diariamente via cron.

Uso:
    python scripts/security_deadline_alert.py              # Envia alertas
    python scripts/security_deadline_alert.py --dry-run    # Mostra sem enviar
"""

import argparse
import json
import logging
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

import msal
import requests
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from env_loader import inject_secrets
from log_config import setup_logging
from collectors.monday_collector import MondayCollector

logger = logging.getLogger(__name__)

DONE_STATUSES = {"Feito", "Concluído", "Concluido", "Done"}
ALERT_DAYS = [5, 2, 1]
RECIPIENT_EMAIL = "wilson.matsumoto@surf.com.br"

CONFIG_FILE = "/opt/weekly-report/config.yaml"


def load_config():
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    inject_secrets(config)
    return config


def collect_security_alerts(boards: list) -> list[dict]:
    """Retorna itens de segurança que vencem em exatamente 5, 2 ou 1 dia."""
    today = datetime.now().date()
    alerts = []

    for board in boards:
        if board.get("category") != "seguranca":
            continue

        items = board.get("filtered_subitems") or board.get("projects") or []
        for item in items:
            status = item.get("status", "")
            if status in DONE_STATUSES:
                continue

            new_due = item.get("new_due_date") or ""
            due = item.get("due_date") or ""
            deadline_str = new_due or due
            if not deadline_str:
                continue

            deadline_source = "Nova Prev. Conclusão" if new_due else "Prev. Conclusão"

            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            days_left = (deadline - today).days
            if days_left not in ALERT_DAYS:
                continue

            alerts.append({
                "board": board.get("board_name", ""),
                "name": item.get("name", ""),
                "group": item.get("parent_name") or item.get("group", ""),
                "status": status,
                "deadline": deadline_str,
                "deadline_formatted": deadline.strftime("%d/%m/%Y"),
                "deadline_source": deadline_source,
                "days_left": days_left,
            })

    alerts.sort(key=lambda a: a["days_left"])
    return alerts


# --------------- Teams Webhook (canal) ---------------

def build_teams_card(alerts: list[dict], dashboard_url: str) -> dict:
    alerts_1d = [a for a in alerts if a["days_left"] == 1]
    alerts_2d = [a for a in alerts if a["days_left"] == 2]
    alerts_5d = [a for a in alerts if a["days_left"] == 5]

    body = [
        {
            "type": "Container",
            "style": "attention",
            "bleed": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": f"🔔 Alerta de Prazos — Segurança ({len(alerts)} {'item' if len(alerts) == 1 else 'itens'})",
                    "weight": "Bolder",
                    "size": "Medium",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"Destinatário: {RECIPIENT_EMAIL}",
                    "spacing": "Small",
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
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Grupo", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Vencimento", "weight": "Bolder", "wrap": True}]},
            {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Tipo Prazo", "weight": "Bolder", "wrap": True}]},
        ],
    }

    def make_rows(items):
        return [{
            "type": "TableRow",
            "cells": [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["name"], "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["group"], "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["deadline_formatted"], "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": a["deadline_source"], "wrap": True}]},
            ],
        } for a in items]

    sections = [
        (alerts_1d, "🔴 Vence AMANHÃ", "Attention"),
        (alerts_2d, "🟡 Vence em 2 dias", "Warning"),
        (alerts_5d, "🟢 Vence em 5 dias", "Good"),
    ]

    for items, title, color in sections:
        if not items:
            continue
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
            "columns": [{"width": 4}, {"width": 2}, {"width": 2}, {"width": 2}],
            "rows": [header_row] + make_rows(items),
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


def send_teams_webhook(webhook_url: str, payload: dict):
    resp = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code in (200, 202):
        logger.info("Teams webhook: alerta enviado ao canal")
    else:
        logger.error("Teams webhook erro: %s - %s", resp.status_code, resp.text)


# --------------- E-mail direto (Graph API) ---------------

def build_email_html(alerts: list[dict], dashboard_url: str) -> str:
    alerts_1d = [a for a in alerts if a["days_left"] == 1]
    alerts_2d = [a for a in alerts if a["days_left"] == 2]
    alerts_5d = [a for a in alerts if a["days_left"] == 5]

    def urgency_emoji(days):
        if days == 1:
            return "🔴"
        if days == 2:
            return "🟡"
        return "🟢"

    def urgency_color(days):
        if days == 1:
            return "#dc2626"
        if days == 2:
            return "#f59e0b"
        return "#22c55e"

    def urgency_bg(days):
        if days == 1:
            return "#fef2f2"
        if days == 2:
            return "#fffbeb"
        return "#f0fdf4"

    rows_html = ""
    for a in alerts:
        bg = urgency_bg(a["days_left"])
        color = urgency_color(a["days_left"])
        emoji = urgency_emoji(a["days_left"])
        if a["days_left"] == 1:
            label = "AMANHÃ"
        else:
            label = f"{a['days_left']} dias"
        rows_html += f"""
        <tr style="background: {bg};">
            <td style="padding: 10px 14px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{a['name']}</td>
            <td style="padding: 10px 14px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">{a['group']}</td>
            <td style="padding: 10px 14px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{a['deadline_formatted']}</td>
            <td style="padding: 10px 14px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">{a['deadline_source']}</td>
            <td style="padding: 10px 14px; border-bottom: 1px solid #e5e7eb; font-weight: 700; color: {color};">{emoji} {label}</td>
        </tr>"""

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #1e293b, #334155); color: white; padding: 20px 24px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0; font-size: 18px;">🔔 Alerta de Prazos — Segurança</h2>
            <p style="margin: 6px 0 0; opacity: 0.8; font-size: 13px;">
                {len(alerts)} {'atividade próxima' if len(alerts) == 1 else 'atividades próximas'} do vencimento
                — Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
        </div>

        <div style="background: #fff; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px; overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #f8fafc;">
                        <th style="padding: 10px 14px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Item</th>
                        <th style="padding: 10px 14px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Grupo</th>
                        <th style="padding: 10px 14px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Vencimento</th>
                        <th style="padding: 10px 14px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Tipo Prazo</th>
                        <th style="padding: 10px 14px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Urgência</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>

            <div style="padding: 16px 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <a href="{dashboard_url}" style="display: inline-block; background: #3b82f6; color: white; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 13px;">📈 Abrir Dashboard</a>
            </div>
        </div>
    </div>"""


def send_email(config: dict, alerts: list[dict], dashboard_url: str):
    """Envia e-mail de alerta direto ao Wilson via Graph API."""
    email_cfg = config.get("email", {})
    tenant_id = email_cfg.get("tenant_id", "")
    client_id = email_cfg.get("client_id", "")
    client_secret = email_cfg.get("client_secret", "")
    user_principal = email_cfg.get("user_principal_name", "")

    if not all([tenant_id, client_id, client_secret, user_principal]):
        logger.error("E-mail: credenciais Graph API incompletas, pulando envio por e-mail")
        return

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        logger.error("E-mail: falha ao obter token: %s", result.get("error_description", ""))
        return
    token = result["access_token"]

    # Monta o e-mail
    alerts_1d = [a for a in alerts if a["days_left"] == 1]
    alerts_2d = [a for a in alerts if a["days_left"] == 2]

    if alerts_1d:
        urgency = "🔴 URGENTE"
    elif alerts_2d:
        urgency = "🟡 ATENÇÃO"
    else:
        urgency = "🟢 AVISO"

    subject = f"{urgency} — {len(alerts)} {'atividade' if len(alerts) == 1 else 'atividades'} de segurança próxima{'s' if len(alerts) != 1 else ''} do vencimento"
    html_body = build_email_html(alerts, dashboard_url)

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": RECIPIENT_EMAIL}}],
        },
        "saveToSentItems": "true",
    }

    url = f"https://graph.microsoft.com/v1.0/users/{user_principal}/sendMail"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        urllib.request.urlopen(req)
        logger.info("E-mail: alerta enviado para %s", RECIPIENT_EMAIL)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error("E-mail: Graph API erro %s: %s", e.code, body[:300])


# --------------- Main ---------------

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Alerta de prazos de segurança via Teams + e-mail")
    parser.add_argument("--dry-run", action="store_true", help="Mostra alertas sem enviar")
    args = parser.parse_args()

    config = load_config()

    logger.info("Coletando projetos Monday.com...")
    monday = MondayCollector(config["monday"])
    boards = monday.collect()

    sec_boards = [b for b in boards if b.get("category") == "seguranca"]
    total_items = sum(
        len(b.get("filtered_subitems") or b.get("projects") or [])
        for b in sec_boards
    )
    logger.info("Segurança: %d boards, %d itens", len(sec_boards), total_items)

    alerts = collect_security_alerts(boards)

    if not alerts:
        logger.info("Nenhum item de segurança vencendo em %s dias.", ALERT_DAYS)
        return

    logger.info("Encontrados %d itens com alerta:", len(alerts))
    for a in alerts:
        logger.info(
            "  [%dd] %s — %s (%s) — %s",
            a["days_left"], a["name"], a["deadline_formatted"],
            a["deadline_source"], a["board"],
        )

    if args.dry_run:
        logger.info("DRY-RUN: Alerta não enviado.")
        return

    dashboard_url = config.get("dashboard", {}).get("base_url", "")

    # 1) Teams webhook (canal)
    webhook_url = config.get("teams", {}).get("webhook_url", "")
    if webhook_url:
        card = build_teams_card(alerts, dashboard_url)
        send_teams_webhook(webhook_url, card)
    else:
        logger.warning("TEAMS_WEBHOOK_URL não configurado, pulando envio ao canal")

    # 2) E-mail direto ao Wilson
    send_email(config, alerts, dashboard_url)


if __name__ == "__main__":
    main()
