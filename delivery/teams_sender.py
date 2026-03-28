"""
Envio de relatório para Microsoft Teams via Power Automate Webhook (Adaptive Card).
"""

import logging

import requests

logger = logging.getLogger(__name__)


class TeamsSender:
    def __init__(self, config: dict):
        self.webhook_url = config["webhook_url"]

    def send(self, report_data: dict, dashboard_url: str):
        """
        Envia resumo do relatório para o Teams via webhook (Adaptive Card com tabelas).

        Args:
            report_data: Dados consolidados do relatório
            dashboard_url: URL do dashboard para link
        """
        otrs_queues = report_data.get("otrs_queues", [])
        if not otrs_queues:
            otrs_queues = [report_data.get("otrs", {})]
        clouds = report_data.get("clouds", [])
        dollar_rate = report_data.get("dollar_rate", 0)
        total_brl = report_data.get("total_cloud_cost_brl", 0)

        period = otrs_queues[0].get("period", {}) if otrs_queues else {}
        period_text = f"{period.get('start', '')} a {period.get('end', '')}"

        # Gera seção de chamados para cada fila
        chamados_body = []
        for q in otrs_queues:
            queue_name = q.get("queue_name", "CLOUD")

            pct_frt = q.get("pct_first_response")
            frt_target = q.get("first_response_target", 24)
            if pct_frt is not None:
                sla_frt_text = f"{pct_frt:.0f}%"
                sla_frt_text += " ✅" if pct_frt >= 90 else " ❌"
            else:
                sla_frt_text = "N/A"

            pct_res = q.get("pct_resolution")
            res_target = q.get("resolution_target", 72)
            if pct_res is not None:
                sla_res_text = f"{pct_res:.0f}%"
                sla_res_text += " ✅" if pct_res >= 90 else " ❌"
            else:
                sla_res_text = "N/A"

            ticket_rows = [
                {
                    "type": "TableRow",
                    "style": "accent",
                    "cells": [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Métrica", "weight": "Bolder", "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Valor", "weight": "Bolder", "wrap": True}]},
                    ],
                },
            ]
            chamados = [
                ("Abertos", str(q.get("opened", 0))),
                ("Fechados", str(q.get("closed", 0))),
                ("Backlog", str(q.get("backlog", 0))),
                (f"1ª Resposta ≤ {frt_target}h (meta: 90%)", sla_frt_text),
                (f"Resolução ≤ {res_target}h (meta: 90%)", sla_res_text),
            ]
            for metrica, valor in chamados:
                ticket_rows.append({
                    "type": "TableRow",
                    "cells": [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": metrica, "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": valor, "wrap": True}]},
                    ],
                })

            chamados_body.append({
                "type": "TextBlock",
                "text": f"🎫 CHAMADOS — Fila {queue_name}",
                "weight": "Bolder",
                "color": "Accent",
                "spacing": "Large",
                "wrap": True,
            })
            chamados_body.append({
                "type": "Table",
                "gridStyle": "accent",
                "firstRowAsHeader": True,
                "showGridLines": True,
                "columns": [{"width": 3}, {"width": 2}],
                "rows": ticket_rows,
            })

        # Tabela de custos
        cloud_rows = [
            {
                "type": "TableRow",
                "style": "accent",
                "cells": [
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Provider", "weight": "Bolder", "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Custo Original", "weight": "Bolder", "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Custo (BRL)", "weight": "Bolder", "wrap": True}]},
                ],
            },
        ]
        for c in clouds:
            original = f"{c.get('currency', 'USD')} {c['total_cost']:,.2f}"
            brl_value = f"BRL {c.get('total_cost_brl', c['total_cost']):,.2f}"
            cloud_rows.append({
                "type": "TableRow",
                "cells": [
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": c["provider"], "weight": "Bolder", "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": original, "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": brl_value, "wrap": True}]},
                ],
            })
        # Linha de total
        cloud_rows.append({
            "type": "TableRow",
            "style": "accent",
            "cells": [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "TOTAL", "weight": "Bolder", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": f"BRL {total_brl:,.2f}", "weight": "Bolder", "wrap": True}]},
            ],
        })

        payload = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": [
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
                                    "items": [{"type": "TextBlock", "text": "📊", "size": "Large"}],
                                    "verticalContentAlignment": "Center",
                                },
                                {
                                    "type": "Column",
                                    "width": "stretch",
                                    "items": [
                                        {"type": "TextBlock", "text": "Relatório Semanal", "weight": "Bolder", "size": "Large", "wrap": True},
                                        {"type": "TextBlock", "text": f"{period_text}", "spacing": "None", "isSubtle": True, "wrap": True},
                                    ],
                                },
                            ],
                        }
                    ],
                },
                *chamados_body,
                {
                    "type": "TextBlock",
                    "text": f"☁️ CUSTOS CLOUD (mês atual) — Câmbio comercial: R$ {dollar_rate:,.4f}",
                    "weight": "Bolder",
                    "color": "Accent",
                    "spacing": "Large",
                    "wrap": True,
                },
                {
                    "type": "Table",
                    "gridStyle": "accent",
                    "firstRowAsHeader": True,
                    "showGridLines": True,
                    "columns": [{"width": 2}, {"width": 1}, {"width": 2}],
                    "rows": cloud_rows,
                },
            ],
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
            self.webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if resp.status_code in (200, 202):
            logger.info("Relatório enviado com sucesso")
        else:
            logger.error("Erro ao enviar: %s - %s", resp.status_code, resp.text)
