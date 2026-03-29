"""
Coletor FinOps OCI — coleta custos com breakdown por compartimento, serviço e
shape de compute, e gera recomendações automáticas baseadas em regras.
"""

import logging
import re
from datetime import datetime, timedelta

import oci
from dateutil.relativedelta import relativedelta
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)

# Limite mínimo para considerar um item de custo relevante (evita ruído de centavos)
_MIN_AMOUNT = 0.001


class OCIFinOpsCollector:
    def __init__(self, config: dict):
        self.tenant_id = config["tenant_id"]
        oci_config = oci.config.from_file()
        self.usage_client = oci.usage_api.UsageapiClient(oci_config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self) -> dict:
        """
        Coleta dados FinOps do mês atual e mês anterior.

        Returns:
            dict com período, custo total, breakdown por compartimento/serviço/shape
            e lista de recomendações.
        """
        today = datetime.utcnow()
        curr_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        curr_end = (today + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        prev_start = curr_start - relativedelta(months=1)
        prev_end = curr_start

        # 1. Compartimentos — mês atual
        comp_items = self._query(curr_start, curr_end, group_by=["compartmentName"])
        comp_totals = self._aggregate_items_by_key(comp_items, "compartment_name")
        total_cost = sum(comp_totals.values())

        by_compartment = sorted(
            [
                {
                    "compartment": name,
                    "cost": round(cost, 2),
                    "pct": round(cost / total_cost * 100, 1) if total_cost else 0.0,
                }
                for name, cost in comp_totals.items()
            ],
            key=lambda x: x["cost"],
            reverse=True,
        )

        # 2. Serviços — mês atual e anterior
        curr_svc_items = self._query(curr_start, curr_end, group_by=["service"])
        prev_svc_items = self._query(prev_start, prev_end, group_by=["service"])

        curr_svc = self._aggregate_items_by_key(curr_svc_items, "service")
        prev_svc = self._aggregate_items_by_key(prev_svc_items, "service")

        # Custo total do mês anterior para calcular variação geral
        prev_total = sum(prev_svc.values())

        # Currency vem do primeiro item disponível
        currency = "BRL"
        for item in curr_svc_items:
            if item.currency:
                currency = item.currency
                break

        all_services = set(curr_svc) | set(prev_svc)
        by_service = []
        for svc in all_services:
            cost = curr_svc.get(svc, 0.0)
            prev_cost = prev_svc.get(svc, 0.0)
            if prev_cost > 0:
                variation_pct = round((cost - prev_cost) / prev_cost * 100, 1)
            else:
                variation_pct = 0.0
            by_service.append(
                {
                    "service": svc,
                    "cost": round(cost, 2),
                    "currency": currency,
                    "prev_cost": round(prev_cost, 2),
                    "variation_pct": variation_pct,
                }
            )
        by_service.sort(key=lambda x: x["cost"], reverse=True)

        # 3. Shapes de compute — mês atual, filtrado por serviço Compute
        shape_items = self._query(
            curr_start, curr_end,
            group_by=["skuName"],
            service_filter="Compute",
        )

        shape_costs: dict[str, dict] = {}
        for item in shape_items:
            if item.computed_amount is None or item.computed_amount <= _MIN_AMOUNT:
                continue
            family = self._parse_shape_family(item.sku_name or "")
            entry = shape_costs.setdefault(family, {"cost": 0.0, "ocpu_hours": 0.0})
            entry["cost"] += item.computed_amount
            if item.computed_quantity and item.unit and "OCPU" in item.unit.upper():
                entry["ocpu_hours"] += item.computed_quantity

        compute_shapes = []
        for family, data in shape_costs.items():
            ocpu_hours = int(data["ocpu_hours"])
            days_elapsed = max((today - curr_start).days, 1)
            est_ocpus = int(ocpu_hours / (days_elapsed * 24)) if days_elapsed else 0
            compute_shapes.append(
                {
                    "shape_family": family,
                    "ocpu_hours": ocpu_hours,
                    "est_ocpus": est_ocpus,
                    "cost": round(data["cost"], 2),
                }
            )
        compute_shapes.sort(key=lambda x: x["cost"], reverse=True)

        # 4. Recomendações
        recommendations = self._build_recommendations(
            by_compartment, by_service, compute_shapes, total_cost
        )

        variation_pct = 0.0
        if prev_total > 0:
            variation_pct = round((total_cost - prev_total) / prev_total * 100, 1)

        return {
            "period": {
                "start": curr_start.strftime("%Y-%m-%d"),
                "end": curr_end.strftime("%Y-%m-%d"),
            },
            "total_cost_brl": round(total_cost, 2),
            "prev_month_cost_brl": round(prev_total, 2),
            "variation_pct": variation_pct,
            "by_compartment": by_compartment,
            "by_service": by_service,
            "compute_shapes": compute_shapes,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Internal query
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _query(self, start: datetime, end: datetime, group_by: list[str], service_filter: str | None = None):
        """
        Executa uma consulta na Usage API do OCI.

        Args:
            start: início do período (inclusive).
            end: fim do período (exclusive).
            group_by: lista de dimensões para agrupamento.
            service_filter: quando informado, filtra pelo nome do serviço.

        Returns:
            Lista de UsageSummary items.
        """
        filters = None
        if service_filter:
            filters = oci.usage_api.models.Filter(
                operator="AND",
                dimensions=[
                    oci.usage_api.models.Dimension(
                        key="service",
                        value=service_filter,
                    )
                ],
            )

        request = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=self.tenant_id,
            time_usage_started=start,
            time_usage_ended=end,
            granularity="DAILY",
            query_type="COST",
            group_by=group_by,
            filter=filters,
        )

        resp = self.usage_client.request_summarized_usages(request)
        return resp.data.items or []

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_items_by_key(items, key_attr: str) -> dict:
        """
        Soma computed_amount agrupando pelo atributo key_attr de cada item.
        Itens com amount None ou <= _MIN_AMOUNT são ignorados.

        Returns:
            dict mapeando o valor do atributo ao custo acumulado.
        """
        totals: dict = {}
        for item in items:
            amount = item.computed_amount
            if amount is None or amount <= _MIN_AMOUNT:
                continue
            key = getattr(item, key_attr) or "Unknown"
            totals[key] = totals.get(key, 0.0) + amount
        return totals

    @staticmethod
    def _parse_shape_family(sku_name: str) -> str:
        """
        Extrai a família do shape a partir do nome do SKU OCI.

        Regras (em ordem de prioridade):
        1. "windows" no nome → "Windows OS Licensing"
        2. Padrão "Oracle OCPU - <Family> - ..." → Family
        3. Padrão GPU\\d+ → família GPU
        4. Default → "Other"
        """
        if not sku_name:
            return "Other"

        lower = sku_name.lower()

        # Regra 1: Windows
        if "windows" in lower:
            return "Windows OS Licensing"

        # Regra 2: Oracle OCPU - <Family> - ...
        match = re.search(r"Oracle OCPU\s*-\s*(\S+)", sku_name, re.IGNORECASE)
        if match:
            return match.group(1)

        # Regra 3: GPU<digits>
        match = re.search(r"GPU(\d+)", sku_name, re.IGNORECASE)
        if match:
            return f"GPU{match.group(1)}"

        return "Other"

    @staticmethod
    def _build_recommendations(
        by_compartment: list[dict],
        by_service: list[dict],
        compute_shapes: list[dict],
        total_cost: float,
    ) -> list[dict]:
        """
        Avalia as 5 regras FinOps e retorna lista de recomendações.

        Cada recomendação contém: severity, title, detail, potential_savings_brl.
        """
        recs = []

        # ------------------------------------------------------------------
        # Regra 1: Windows Licensing > 10% do custo total
        # ------------------------------------------------------------------
        windows_cost = sum(
            s["cost"] for s in compute_shapes
            if s["shape_family"] == "Windows OS Licensing"
        )
        if total_cost > 0 and windows_cost / total_cost > 0.10:
            pct = round(windows_cost / total_cost * 100, 1)
            savings = round(windows_cost * 0.30, 2)  # estimativa de economia com BYOL
            recs.append(
                {
                    "severity": "warning",
                    "title": f"Windows OS Licensing representa {pct}% do custo total",
                    "detail": (
                        f"Custo de licenciamento Windows: R$ {windows_cost:.2f}. "
                        "Considere migrar para BYOL (Bring Your Own License) ou "
                        "adotar alternativas Linux para reduzir custos."
                    ),
                    "potential_savings_brl": savings,
                }
            )

        # ------------------------------------------------------------------
        # Regra 2: OKE Enhanced clusters detectados
        # ------------------------------------------------------------------
        oke_services = [s for s in by_service if "OKE" in s["service"].upper() and "ENHANCED" in s["service"].upper()]
        if oke_services:
            oke_cost = sum(s["cost"] for s in oke_services)
            recs.append(
                {
                    "severity": "info",
                    "title": "OKE Enhanced Clusters detectados",
                    "detail": (
                        f"Custo com OKE Enhanced: R$ {oke_cost:.2f}. "
                        "Clusters OKE Enhanced têm custo adicional. "
                        "Avalie se os recursos avançados estão sendo utilizados ou "
                        "se a migração para clusters básicos é viável."
                    ),
                    "potential_savings_brl": 0.0,
                }
            )

        # ------------------------------------------------------------------
        # Regra 3: Compartimento único > 60% do custo total
        # ------------------------------------------------------------------
        for comp in by_compartment:
            if comp["pct"] > 60.0:
                recs.append(
                    {
                        "severity": "info",
                        "title": f"Custo concentrado no compartimento '{comp['compartment']}'",
                        "detail": (
                            f"O compartimento '{comp['compartment']}' representa "
                            f"{comp['pct']}% do custo total (R$ {comp['cost']:.2f}). "
                            "Alta concentração pode indicar falta de governança ou "
                            "recursos não distribuídos adequadamente entre ambientes."
                        ),
                        "potential_savings_brl": 0.0,
                    }
                )
                break  # Reporta apenas o primeiro compartimento concentrado

        # ------------------------------------------------------------------
        # Regra 4: Variação de serviço > 30% E custo anterior > 100
        # ------------------------------------------------------------------
        for svc in by_service:
            if svc["variation_pct"] > 30.0 and svc["prev_cost"] > 100.0:
                diff = round(svc["cost"] - svc["prev_cost"], 2)
                recs.append(
                    {
                        "severity": "warning",
                        "title": f"Anomalia de custo detectada em {svc['service']}",
                        "detail": (
                            f"Serviço '{svc['service']}' teve variação de "
                            f"{svc['variation_pct']}% em relação ao mês anterior "
                            f"(R$ {svc['prev_cost']:.2f} → R$ {svc['cost']:.2f}, "
                            f"delta: R$ {diff:.2f}). Verifique recursos provisionados recentemente."
                        ),
                        "potential_savings_brl": round(max(diff, 0.0), 2),
                    }
                )

        # ------------------------------------------------------------------
        # Regra 5: MySQL Storage > 40% do custo MySQL total
        # ------------------------------------------------------------------
        mysql_services = [s for s in by_service if "MYSQL" in s["service"].upper()]
        mysql_storage = [
            s for s in mysql_services
            if "STORAGE" in s["service"].upper()
        ]
        mysql_total_cost = sum(s["cost"] for s in mysql_services)
        mysql_storage_cost = sum(s["cost"] for s in mysql_storage)

        if mysql_total_cost > 0 and mysql_storage_cost / mysql_total_cost > 0.40:
            pct = round(mysql_storage_cost / mysql_total_cost * 100, 1)
            recs.append(
                {
                    "severity": "info",
                    "title": f"MySQL: alto custo de storage ({pct}% do total MySQL)",
                    "detail": (
                        f"O custo de storage MySQL representa {pct}% do custo total MySQL "
                        f"(R$ {mysql_storage_cost:.2f} de R$ {mysql_total_cost:.2f}). "
                        "Avalie políticas de retenção de backups, compressão de dados "
                        "ou migração para armazenamento em camadas."
                    ),
                    "potential_savings_brl": round(mysql_storage_cost * 0.20, 2),
                }
            )

        return recs
