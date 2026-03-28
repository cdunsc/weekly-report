"""
Coletor de custos AWS via Cost Explorer.
Conta Payer: custo consolidado + breakdown por linked account.
"""

import logging

import boto3
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)


class AWSCollector:
    def __init__(self, config: dict):
        self.client = boto3.client("ce", region_name="us-east-1")

    def _get_date_range(self) -> tuple[str, str]:
        """Retorna primeiro dia do mês atual e amanhã (exclusive)."""
        today = datetime.now()
        start = today.replace(day=1).strftime("%Y-%m-%d")
        # Cost Explorer end date é exclusive — usa amanhã para incluir dados de hoje
        end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        return start, end

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
           before_sleep=before_sleep_log(logger, logging.WARNING))
    def _query_costs(self, group_by: list = None, filter_expr: dict = None) -> dict:
        """Consulta Cost Explorer."""
        start, end = self._get_date_range()

        params = {
            "TimePeriod": {"Start": start, "End": end},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
        }
        if group_by:
            params["GroupBy"] = group_by
        if filter_expr:
            params["Filter"] = filter_expr

        return self.client.get_cost_and_usage(**params)

    def collect(self) -> dict:
        """
        Coleta custos AWS do mês atual.

        Returns:
            dict com custo total consolidado e breakdown por conta e por serviço.
        """
        start, end = self._get_date_range()

        # 1. Custo total consolidado
        total_resp = self._query_costs()
        total_cost = 0.0
        currency = "USD"
        for result in total_resp.get("ResultsByTime", []):
            amount = result["Total"]["UnblendedCost"]["Amount"]
            currency = result["Total"]["UnblendedCost"]["Unit"]
            total_cost += float(amount)

        # 2. Breakdown por conta (linked accounts) — soma DAILY
        account_resp = self._query_costs(
            group_by=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}]
        )
        account_totals = {}
        for result in account_resp.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                account_id = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                account_totals[account_id] = account_totals.get(account_id, 0.0) + amount

        accounts = [
            {"account_id": aid, "cost": round(cost, 2)}
            for aid, cost in account_totals.items()
            if cost > 0.01
        ]

        # Resolve nomes das contas
        try:
            org_client = boto3.client("organizations")
            for acc in accounts:
                try:
                    info = org_client.describe_account(AccountId=acc["account_id"])
                    acc["account_name"] = info["Account"]["Name"]
                except Exception:
                    acc["account_name"] = acc["account_id"]
        except Exception:
            for acc in accounts:
                acc["account_name"] = acc["account_id"]

        accounts.sort(key=lambda x: x["cost"], reverse=True)

        # 3. Breakdown por serviço (top 10) — soma DAILY
        service_resp = self._query_costs(
            group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}]
        )
        service_totals = {}
        for result in service_resp.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                service_name = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                service_totals[service_name] = service_totals.get(service_name, 0.0) + amount

        services = [
            {"service": name, "cost": round(cost, 2)}
            for name, cost in service_totals.items()
            if cost > 0.01
        ]

        services.sort(key=lambda x: x["cost"], reverse=True)

        return {
            "provider": "AWS",
            "period": {"start": start, "end": end},
            "currency": currency,
            "total_cost": round(total_cost, 2),
            "accounts": accounts,
            "top_services": services[:10],
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
           before_sleep=before_sleep_log(logger, logging.WARNING))
    def collect_monthly(self, months: int = 3) -> list[dict]:
        """
        Coleta custo total dos últimos N meses completos.

        Returns:
            Lista de dicts com {month: "2026-01", cost: float, currency: str}
        """
        from dateutil.relativedelta import relativedelta

        today = datetime.now()
        # Primeiro dia do mês atual (exclusive end)
        current_month_start = today.replace(day=1)
        # Primeiro dia de N meses atrás
        start = current_month_start - relativedelta(months=months)

        resp = self.client.get_cost_and_usage(
            TimePeriod={
                "Start": start.strftime("%Y-%m-%d"),
                "End": current_month_start.strftime("%Y-%m-%d"),
            },
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )

        results = []
        for period in resp.get("ResultsByTime", []):
            month_start = period["TimePeriod"]["Start"]  # "2026-01-01"
            amount = float(period["Total"]["UnblendedCost"]["Amount"])
            currency = period["Total"]["UnblendedCost"]["Unit"]
            results.append({
                "month": month_start[:7],  # "2026-01"
                "cost": round(amount, 2),
                "currency": currency,
            })

        return results
