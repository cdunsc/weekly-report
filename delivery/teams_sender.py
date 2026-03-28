"""
Envio de relatório para Microsoft Teams via Power Automate Webhook (Adaptive Card).
"""

import logging

import requests

logger = logging.getLogger(__name__)


class TeamsSender:
    def __init__(self, config: dict):
        self.webhook_url = config["webhook_url"]

    @staticmethod
    def _delta_text(deltas: dict, key: str) -> str:
        """Returns delta indicator string like ' ▲ +12.1%' or empty string."""
        d = deltas.get(key, {})
        pct = d.get("pct")
        if pct is None:
            return ""
        arrow = "▲" if pct > 0 else "▼" if pct < 0 else ""
        return f" {arrow} {pct:+.1f}%" if pct != 0 else ""

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

        deltas = report_data.get("deltas", {})

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
            # Build delta indicators for this queue
            q_opened_delta = self._delta_text(deltas, f"{queue_name}_opened")
            q_closed_delta = self._delta_text(deltas, f"{queue_name}_closed")
            q_backlog_delta = self._delta_text(deltas, f"{queue_name}_backlog")

            chamados = [
                ("Abertos", f"{q.get('opened', 0)}{q_opened_delta}"),
                ("Fechados", f"{q.get('closed', 0)}{q_closed_delta}"),
                ("Backlog", f"{q.get('backlog', 0)}{q_backlog_delta}"),
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
            provider = c["provider"]
            original = f"{c.get('currency', 'USD')} {c['total_cost']:,.2f}"
            brl_value = f"BRL {c.get('total_cost_brl', c['total_cost']):,.2f}"
            cost_delta = self._delta_text(deltas, f"cost_{provider}")
            brl_display = f"{brl_value}{cost_delta}" if cost_delta else brl_value
            cloud_rows.append({
                "type": "TableRow",
                "cells": [
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": provider, "weight": "Bolder", "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": original, "wrap": True}]},
                    {"type": "TableCell", "items": [{"type": "TextBlock", "text": brl_display, "wrap": True}]},
                ],
            })
        # Linha de total
        total_delta = self._delta_text(deltas, "cost_total")
        total_display = f"BRL {total_brl:,.2f}{total_delta}"
        cloud_rows.append({
            "type": "TableRow",
            "style": "accent",
            "cells": [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "TOTAL", "weight": "Bolder", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": total_display, "weight": "Bolder", "wrap": True}]},
            ],
        })

        # Top 3 contas AWS (se disponível)
        aws_accounts_body = []
        for c in clouds:
            if c.get("provider") == "AWS" and c.get("accounts"):
                top3 = c["accounts"][:3]
                if top3:
                    lines = [f"  {i+1}. {a.get('account_name', a.get('account_id', 'N/A'))} — USD {a['cost']:,.2f}" for i, a in enumerate(top3)]
                    aws_accounts_body.append({
                        "type": "TextBlock",
                        "text": "💰 Top Contas AWS:\n" + "\n".join(lines),
                        "wrap": True,
                        "spacing": "Small",
                        "isSubtle": True,
                    })
                break

        # Seção Monday.com (projetos)
        monday_boards = report_data.get("monday_boards", [])
        monday_body = []
        if monday_boards:
            monday_body.append({
                "type": "TextBlock",
                "text": "📋 PROJETOS (Monday.com)",
                "weight": "Bolder",
                "color": "Accent",
                "spacing": "Large",
                "wrap": True,
            })
            proj_rows = [
                {
                    "type": "TableRow",
                    "style": "accent",
                    "cells": [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Board", "weight": "Bolder", "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Total", "weight": "Bolder", "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Feitos", "weight": "Bolder", "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "%", "weight": "Bolder", "wrap": True}]},
                    ],
                },
            ]
            for board in monday_boards:
                done = sum(board.get("status_summary", {}).get(s, 0) for s in ("Feito", "Concluído", "Done"))
                total = board.get("total_projects", 0)
                pct = f"{round(done / total * 100)}%" if total > 0 else "0%"
                proj_rows.append({
                    "type": "TableRow",
                    "cells": [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": board["board_name"], "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": str(total), "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": str(done), "wrap": True}]},
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": pct, "wrap": True}]},
                    ],
                })
            monday_body.append({
                "type": "Table",
                "gridStyle": "accent",
                "firstRowAsHeader": True,
                "showGridLines": True,
                "columns": [{"width": 3}, {"width": 1}, {"width": 1}, {"width": 1}],
                "rows": proj_rows,
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
                *aws_accounts_body,
                *monday_body,
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
