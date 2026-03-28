"""
Coletor de custos Golden Cloud via web scraping do portal.
Login no portal e consulta da API /Analysis/Summary.
"""

import json
import os
import re
import warnings
import requests
from datetime import datetime

warnings.filterwarnings("ignore", message="Unverified HTTPS request")


DATA_FILE = "/opt/weekly-report/data/golden_cloud.json"


class GoldenCloudCollector:
    def __init__(self, config: dict):
        self.mode = config.get("mode", "scraping")
        self.portal_url = config.get("portal_url", "")
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.data_file = DATA_FILE

    def _scrape(self) -> dict:
        """Login no portal e coleta custos via API interna."""
        session = requests.Session()
        session.verify = False

        # GET login page para obter cookies e token antiforgery
        login_page = session.get(self.portal_url, timeout=30)
        token_match = re.search(
            r'name="__RequestVerificationToken".*?value="([^"]+)"',
            login_page.text,
        )
        if not token_match:
            raise RuntimeError("Não foi possível obter token antiforgery do portal Golden Cloud")

        token = token_match.group(1)

        # POST login
        login_resp = session.post(
            self.portal_url,
            data={
                "Email": self.username,
                "Password": self.password,
                "__RequestVerificationToken": token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
            timeout=60,
        )

        if login_resp.status_code not in (200, 302):
            raise RuntimeError(f"Falha no login Golden Cloud: HTTP {login_resp.status_code}")

        # GET dados de consumo
        summary_resp = session.get(
            f"{self.portal_url.rstrip('/')}/Analysis/Summary",
            timeout=60,
        )
        summary_resp.raise_for_status()
        data = summary_resp.json()

        # Charts[1] = "Consumption of the Month"
        month_chart = data["Charts"][1]
        total_cost = float(month_chart["DataSets"][0]["Data"][0])
        currency = month_chart["Currency"][0] if month_chart.get("Currency") else "BRL"

        # Charts[2] = histórico mensal (últimos 6 meses)
        history_chart = data["Charts"][2]
        history = []
        for i, label in enumerate(history_chart["Labels"]):
            for ds in history_chart["DataSets"]:
                if ds["Label"] == "VMWare" and i < len(ds["Data"]):
                    history.append({
                        "month": label,
                        "cost": round(float(ds["Data"][i]), 2),
                    })

        return {
            "total_cost": round(total_cost, 2),
            "currency": currency,
            "history": history,
            "dollar_quote": month_chart.get("DollarQuote", ""),
        }

    def save_manual_input(self, total_cost: float, currency: str = "BRL",
                          details: list = None):
        """Salva dados inseridos manualmente via dashboard."""
        data = {
            "updated_at": datetime.now().isoformat(),
            "total_cost": total_cost,
            "currency": currency,
            "details": details or [],
        }

        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)

    def collect(self) -> dict:
        """Coleta custos Golden Cloud."""
        today = datetime.now()
        period = {
            "start": today.replace(day=1).strftime("%Y-%m-%d"),
            "end": today.strftime("%Y-%m-%d"),
        }

        if self.mode == "scraping" and self.portal_url:
            try:
                scraped = self._scrape()

                # Salva cache local
                cache = {
                    "updated_at": datetime.now().isoformat(),
                    "total_cost": scraped["total_cost"],
                    "currency": scraped["currency"],
                    "history": scraped.get("history", []),
                    "dollar_quote": scraped.get("dollar_quote", ""),
                }
                os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
                with open(self.data_file, "w") as f:
                    json.dump(cache, f, indent=2)

                return {
                    "provider": "Golden Cloud",
                    "period": period,
                    "currency": scraped["currency"],
                    "total_cost": scraped["total_cost"],
                    "details": scraped.get("history", []),
                    "status": "OK",
                }
            except Exception as e:
                print(f"[GOLDEN] Scraping falhou ({e}), usando cache local")
                # Fallback para cache

        # Fallback: input manual
        if not os.path.exists(self.data_file):
            return {
                "provider": "Golden Cloud",
                "period": period,
                "currency": "BRL",
                "total_cost": 0.0,
                "details": [],
                "status": "SEM DADOS - Inserir manualmente no dashboard",
            }

        with open(self.data_file) as f:
            data = json.load(f)

        return {
            "provider": "Golden Cloud",
            "period": period,
            "currency": data.get("currency", "BRL"),
            "total_cost": data.get("total_cost", 0.0),
            "details": data.get("details", []),
            "updated_at": data.get("updated_at", ""),
            "status": "OK",
        }
