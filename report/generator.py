"""
Gerador de relatório: consolida dados e renderiza templates.
"""

import calendar
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

    def generate(self, otrs_data: dict, cloud_costs: list, monday_boards: list = None, otrs_queues: list = None, otrs_daily_queues: list = None, save_history: bool = True, monthly_costs: dict = None, finops_data: dict = None, collector_metrics: dict = None) -> dict:
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

        # Extrai detalhes de custo por provider (para templates)
        cloud_details = {}
        for c in cloud_costs:
            provider = c.get("provider", "")
            detail = {
                "total_cost": c["total_cost"],
                "currency": c.get("currency", "USD"),
                "total_cost_brl": c.get("total_cost_brl", c["total_cost"]),
            }
            if c.get("accounts"):
                detail["accounts"] = c["accounts"]
            if c.get("top_services"):
                detail["top_services"] = c["top_services"]
            cloud_details[provider] = detail

        report_data = {
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "otrs": otrs_data,
            "clouds": cloud_costs,
            "cloud_details": cloud_details,
            "total_cloud_cost_brl": round(total_brl, 2),
            "dollar_rate": dollar_rate,
            "dashboard_url": self.base_url,
            "monday_boards": monday_boards or [],
            "otrs_queues": otrs_queues or [],
            "otrs_daily_queues": otrs_daily_queues or [],
            "monthly_costs": monthly_costs or {},
            "finops": finops_data,
        }

        # Salva dados brutos para histórico (apenas no relatório semanal)
        if save_history:
            self._save_history(report_data)

        # Carrega histórico para gráficos
        history = self._load_history()
        report_data["deltas"] = self._calc_deltas(report_data, history)
        report_data["history"] = history

        # Forecast de custo mensal
        report_data["forecasts"] = self._calc_forecasts(cloud_costs, total_brl)

        # Cloud Efficiency Score
        report_data["efficiency_score"] = self._calc_efficiency_score(report_data)

        # Métricas dos coletores
        report_data["collector_metrics"] = collector_metrics or {}

        # Gera dashboard HTML legado (mantido como backup, React SPA é o index.html)
        os.makedirs(self.output_dir, exist_ok=True)
        dashboard_path = os.path.join(self.output_dir, "dashboard_legacy.html")
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

    @staticmethod
    def save_report_json(report_data: dict, output_path: str):
        """Salva dados do relatório como JSON para o frontend React."""
        import copy
        data = copy.deepcopy(report_data)
        # Remove campos não serializáveis ou desnecessários
        for key in list(data.keys()):
            if key == "history":
                # Mantém só últimas 12 semanas para o frontend
                data[key] = data[key][-12:]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    @staticmethod
    def _calc_forecasts(cloud_costs: list, total_brl: float) -> dict:
        """Calcula forecast de custo mensal por provider."""
        now = datetime.now()
        days_elapsed = now.day
        days_total = calendar.monthrange(now.year, now.month)[1]

        forecasts = {}
        for c in cloud_costs:
            provider = c.get("provider", "")
            accumulated = c.get("total_cost_brl", c.get("total_cost", 0.0))
            if days_elapsed > 0:
                estimated = round(accumulated / days_elapsed * days_total, 2)
            else:
                estimated = 0.0
            forecasts[provider] = {
                "accumulated_brl": round(accumulated, 2),
                "estimated_brl": estimated,
                "days_elapsed": days_elapsed,
                "days_total": days_total,
            }

        # Total across all providers
        if days_elapsed > 0:
            total_estimated = round(total_brl / days_elapsed * days_total, 2)
        else:
            total_estimated = 0.0
        forecasts["total"] = {
            "accumulated_brl": round(total_brl, 2),
            "estimated_brl": total_estimated,
            "days_elapsed": days_elapsed,
            "days_total": days_total,
        }

        return forecasts

    @staticmethod
    def _calc_efficiency_score(report_data: dict) -> int | None:
        """Calcula Cloud Efficiency Score (0-100) com base em recomendações e SLA."""
        finops = report_data.get("finops")
        if finops is None:
            return None

        score = 100

        # Analisa recomendações FinOps
        recommendations = finops.get("recommendations", [])
        anomalia_deductions = 0
        for rec in recommendations:
            title = rec.get("title", "")
            detail = rec.get("detail", "")
            if "Windows" in title:
                score -= 15
            if "concentra" in title.lower():
                score -= 10
            if "anomalia" in title.lower():
                if anomalia_deductions < 20:
                    deduct = min(10, 20 - anomalia_deductions)
                    score -= deduct
                    anomalia_deductions += deduct
            if "OKE" in title:
                score -= 5
            if "MySQL" in title and "storage" in detail:
                score -= 5

        # Analisa SLA da primeira fila
        otrs_queues = report_data.get("otrs_queues", [])
        if otrs_queues:
            first_queue = otrs_queues[0]
            pct_first_response = first_queue.get("pct_first_response")
            pct_resolution = first_queue.get("pct_resolution")
            if pct_first_response is not None and pct_first_response < 90:
                score -= 10
            if pct_resolution is not None and pct_resolution < 90:
                score -= 10

        return max(0, score)

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

        # Fallback: última cotação do histórico
        history = self._load_history()
        for entry in reversed(history):
            rate = entry.get("dollar_rate")
            if rate and isinstance(rate, (int, float)) and rate > 0:
                logger.warning(f"Usando cotação do histórico: {rate}")
                return rate

        logger.error("Sem cotação disponível, usando fallback 5.25")
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

        cloud_details = {}
        for c in report_data["clouds"]:
            provider = c["provider"]
            detail = {
                "total_cost": c["total_cost"],
                "currency": c.get("currency", "USD"),
                "total_cost_brl": c.get("total_cost_brl", c["total_cost"]),
            }
            if c.get("accounts"):
                detail["accounts"] = [
                    {"name": a.get("account_name", a.get("account_id", "")), "cost": a["cost"]}
                    for a in c["accounts"][:10]
                ]
            if c.get("top_services"):
                detail["top_services"] = [
                    {"service": s["service"], "cost": s["cost"]}
                    for s in c["top_services"][:5]
                ]
            cloud_details[provider] = detail

        entry = {
            "date": report_data["generated_at"],
            "period": report_data["otrs"].get("period", {}),
            # Mantém campos legados para compatibilidade
            "opened": report_data["otrs"].get("opened", 0),
            "closed": report_data["otrs"].get("closed", 0),
            "backlog": report_data["otrs"].get("backlog", 0),
            "avg_first_response": report_data["otrs"].get("avg_first_response_hours"),
            "avg_resolution": report_data["otrs"].get("avg_resolution_hours"),
            "dollar_rate": report_data.get("dollar_rate"),
            "cloud_costs": {
                c["provider"]: c["total_cost"] for c in report_data["clouds"]
            },
            "cloud_details": cloud_details,
            "queues": queues_snapshot,
        }

        history.append(entry)
        # Mantém últimas 52 semanas
        history = history[-52:]

        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

    def _calc_deltas(self, report_data: dict, history: list) -> dict:
        """Calcula variação percentual vs semana anterior."""
        deltas = {}
        if len(history) < 1:
            return deltas

        prev = history[-1]

        # Delta custos por provider
        prev_costs = prev.get("cloud_costs", {})
        for c in report_data["clouds"]:
            provider = c["provider"]
            current = c.get("total_cost_brl", c["total_cost"])
            previous = prev_costs.get(provider, 0)
            if previous > 0:
                pct = round((current - previous) / previous * 100, 1)
                deltas[f"cost_{provider}"] = {"current": current, "previous": previous, "pct": pct}

        # Delta total
        current_total = report_data.get("total_cloud_cost_brl", 0)
        prev_total = sum(prev_costs.values()) if prev_costs else 0
        if prev_total > 0:
            deltas["cost_total"] = {
                "current": current_total,
                "previous": prev_total,
                "pct": round((current_total - prev_total) / prev_total * 100, 1),
            }

        # Delta chamados por fila
        prev_queues = prev.get("queues", {})
        for q in report_data.get("otrs_queues", []):
            qname = q["queue_name"]
            prev_q = prev_queues.get(qname, {})
            for field in ("opened", "closed", "backlog"):
                curr_val = q.get(field, 0)
                prev_val = prev_q.get(field, 0)
                if prev_val > 0:
                    pct = round((curr_val - prev_val) / prev_val * 100, 1)
                elif curr_val > 0:
                    pct = 100.0
                else:
                    pct = 0.0
                deltas[f"{qname}_{field}"] = {"current": curr_val, "previous": prev_val, "pct": pct}

        return deltas

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
