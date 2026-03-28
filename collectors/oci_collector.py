"""
Coletor de custos OCI via Usage API.
Conta única: custo consolidado + breakdown por serviço.
"""

import logging

import oci
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)


class OCICollector:
    def __init__(self, config: dict):
        self.tenant_id = config["tenant_id"]
        oci_config = oci.config.from_file()
        self.usage_client = oci.usage_api.UsageapiClient(oci_config)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
           before_sleep=before_sleep_log(logger, logging.WARNING))
    def collect(self) -> dict:
        """
        Coleta custos OCI do mês atual.

        Returns:
            dict com custo total e breakdown por serviço.
        """
        today = datetime.utcnow()
        start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # end = amanhã para incluir dados de hoje (end é exclusive na API)
        end = (today + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # Custo total — usa DAILY e soma para bater com o console OCI
        total_request = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=self.tenant_id,
            time_usage_started=start,
            time_usage_ended=end,
            granularity="DAILY",
            query_type="COST",
        )

        total_resp = self.usage_client.request_summarized_usages(total_request)
        total_cost = 0.0
        currency = "USD"

        for item in total_resp.data.items:
            if item.computed_amount is not None:
                total_cost += item.computed_amount
                currency = item.currency or currency

        # Breakdown por serviço — DAILY agrupado por serviço e somado
        service_request = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=self.tenant_id,
            time_usage_started=start,
            time_usage_ended=end,
            granularity="DAILY",
            query_type="COST",
            group_by=["service"],
        )

        service_resp = self.usage_client.request_summarized_usages(service_request)
        service_totals = {}

        for item in service_resp.data.items:
            if item.computed_amount and item.computed_amount > 0.01:
                name = item.service or "Unknown"
                service_totals[name] = service_totals.get(name, 0.0) + item.computed_amount

        services = [
            {"service": name, "cost": round(cost, 2)}
            for name, cost in service_totals.items()
        ]

        services.sort(key=lambda x: x["cost"], reverse=True)

        return {
            "provider": "OCI",
            "period": {
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
            },
            "currency": currency,
            "total_cost": round(total_cost, 2),
            "top_services": services[:10],
        }
