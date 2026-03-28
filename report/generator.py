"""
Gerador de relatório: consolida dados e renderiza templates.
"""

import json
import logging
import os
import requests
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
DATA_DIR = "/opt/weekly-report/data"


class ReportGenerator:
    def __init__(self, config: dict):
        self.output_dir = config["dashboard"]["output_dir"]
        self.base_url = config["dashboard"].get("base_url", "")
        self.env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

    def generate(self, otrs_data: dict, cloud_costs: list, monday_boards: list = None, otrs_queues: list = None, otrs_daily_queues: list = None, save_history: bool = True) -> dict:
        """
        Gera o relatório completo.

        Args:
            otrs_data: Dados do OTRS collector
            cloud_costs: Lista de dicts dos cloud collectors [aws, oci, golden]

        Returns:
            dict com paths dos arquivos gerados
        """
        # Cotação do dólar (PTAX BCB)
        dollar_rate = self._get_dollar_rate()

        # Converte custos em USD para BRL e calcula total em BRL
        total_brl = 0.0
        for c in cloud_costs:
            if c.get("currency", "USD") == "USD":
                c["total_cost_brl"] = round(c["total_cost"] * dollar_rate, 2)
            else:
                c["total_cost_brl"] = c["total_cost"]
            total_brl += c["total_cost_brl"]

        report_data = {
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "otrs": otrs_data,
            "clouds": cloud_costs,
            "total_cloud_cost_brl": round(total_brl, 2),
            "dollar_rate": dollar_rate,
            "dashboard_url": self.base_url,
            "monday_boards": monday_boards or [],
            "otrs_queues": otrs_queues or [],
            "otrs_daily_queues": otrs_daily_queues or [],
        }

        # Salva dados brutos para histórico (apenas no relatório semanal)
        if save_history:
            self._save_history(report_data)

        # Carrega histórico para gráficos
        history = self._load_history()
        report_data["history"] = history

        # Gera dashboard HTML
        os.makedirs(self.output_dir, exist_ok=True)
        dashboard_path = os.path.join(self.output_dir, "index.html")
        template = self.env.get_template("dashboard.html")
        html = template.render(**report_data)

        with open(dashboard_path, "w") as f:
            f.write(html)

        # Gera e-mail HTML
        email_template = self.env.get_template("email.html")
        email_html = email_template.render(**report_data)

        return {
            "dashboard_path": dashboard_path,
            "email_html": email_html,
            "report_data": report_data,
        }

    def _get_dollar_rate(self) -> float:
        """Busca cotação comercial USD/BRL via Frankfurter API (taxas do BCE)."""
        try:
            resp = requests.get(
                "https://api.frankfurter.app/latest?from=USD&to=BRL",
                timeout=10,
            )
            data = resp.json()
            return data["rates"]["BRL"]
        except Exception:
            pass

        # Fallback: PTAX do Banco Central
        today = datetime.now()
        for i in range(5):
            date = (today - timedelta(days=i)).strftime("%m-%d-%Y")
            url = (
                f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
                f"CotacaoDolarDia(dataCotacao=@dataCotacao)"
                f"?@dataCotacao='{date}'&$format=json"
            )
            try:
                resp = requests.get(url, timeout=10)
                data = resp.json()
                if data.get("value"):
                    return data["value"][-1]["cotacaoVenda"]
            except Exception:
                continue

        logger.warning("Erro ao obter cotação do dólar, usando fallback 5.25")
        return 5.25

    def _save_history(self, report_data: dict):
        """Salva snapshot semanal para histórico (por fila)."""
        os.makedirs(DATA_DIR, exist_ok=True)
        history_file = os.path.join(DATA_DIR, "history.json")

        history = []
        if os.path.exists(history_file):
            with open(history_file) as f:
                history = json.load(f)

        # Dados por fila
        queues_snapshot = {}
        for q in report_data.get("otrs_queues", []):
            queues_snapshot[q["queue_name"]] = {
                "opened": q.get("opened", 0),
                "closed": q.get("closed", 0),
                "backlog": q.get("backlog", 0),
                "avg_first_response": q.get("avg_first_response_hours"),
                "avg_resolution": q.get("avg_resolution_hours"),
                "pct_first_response": q.get("pct_first_response"),
                "pct_resolution": q.get("pct_resolution"),
            }

        entry = {
            "date": report_data["generated_at"],
            "period": report_data["otrs"].get("period", {}),
            # Mantém campos legados para compatibilidade
            "opened": report_data["otrs"].get("opened", 0),
            "closed": report_data["otrs"].get("closed", 0),
            "backlog": report_data["otrs"].get("backlog", 0),
            "avg_first_response": report_data["otrs"].get("avg_first_response_hours"),
            "avg_resolution": report_data["otrs"].get("avg_resolution_hours"),
            "cloud_costs": {
                c["provider"]: c["total_cost"] for c in report_data["clouds"]
            },
            "queues": queues_snapshot,
        }

        history.append(entry)
        # Mantém últimas 52 semanas
        history = history[-52:]

        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

    def _load_history(self) -> list:
        """Carrega histórico de relatórios anteriores com validação."""
        history_file = os.path.join(DATA_DIR, "history.json")
        if not os.path.exists(history_file):
            return []
        try:
            with open(history_file) as f:
                data = json.load(f)
            if not isinstance(data, list):
                logger.warning("history.json não é uma lista, ignorando")
                return []
            valid = []
            for entry in data:
                if isinstance(entry, dict) and "date" in entry:
                    valid.append(entry)
                else:
                    logger.warning(f"Entrada inválida no histórico ignorada: {entry}")
            return valid
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Erro ao carregar history.json: {e}")
            return []
