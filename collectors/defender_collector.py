"""
Coletor Microsoft Defender for Endpoint via Graph API e WindowsDefenderATP API.
Coleta: alertas, incidentes, secure score, vulnerabilidades, dispositivos e recomendações.
"""

import logging
from datetime import datetime, timedelta

import msal
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.microsoft.com/v1.0"
DEFENDER_URL = "https://api.securitycenter.microsoft.com/api"


class DefenderCollector:
    def __init__(self, config: dict):
        self.tenant_id = config["tenant_id"]
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self._graph_token = None
        self._defender_token = None

    def _get_token(self, scope: str) -> str:
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=[scope])
        if "access_token" not in result:
            raise RuntimeError(f"Token error ({scope}): {result.get('error_description', '')}")
        return result["access_token"]

    @property
    def graph_token(self) -> str:
        if not self._graph_token:
            self._graph_token = self._get_token("https://graph.microsoft.com/.default")
        return self._graph_token

    @property
    def defender_token(self) -> str:
        if not self._defender_token:
            self._defender_token = self._get_token("https://api.securitycenter.microsoft.com/.default")
        return self._defender_token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15),
           before_sleep=before_sleep_log(logger, logging.WARNING))
    def _graph_get(self, path: str, params: dict = None) -> dict:
        resp = requests.get(
            f"{GRAPH_URL}{path}",
            headers={"Authorization": f"Bearer {self.graph_token}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15),
           before_sleep=before_sleep_log(logger, logging.WARNING))
    def _defender_get(self, path: str, params: dict = None) -> dict:
        resp = requests.get(
            f"{DEFENDER_URL}{path}",
            headers={"Authorization": f"Bearer {self.defender_token}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def collect(self) -> dict:
        """Coleta todos os dados do Defender e retorna dict consolidado."""
        data = {
            "collected_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "alerts": self._collect_alerts(),
            "incidents": self._collect_incidents(),
            "secure_score": self._collect_secure_score(),
            "devices": self._collect_devices(),
            "vulnerabilities": self._collect_vulnerabilities(),
            "recommendations": self._collect_recommendations(),
        }

        # Calcula resumos
        data["summary"] = self._build_summary(data)

        return data

    def _collect_alerts(self) -> list[dict]:
        """Alertas dos últimos 30 dias."""
        since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            result = self._defender_get("/alerts", params={
                "$filter": f"alertCreationTime ge {since}",
                "$top": 500,
                "$orderby": "alertCreationTime desc",
            })
            alerts = []
            for a in result.get("value", []):
                alerts.append({
                    "id": a.get("id", ""),
                    "title": a.get("title", ""),
                    "severity": a.get("severity", "").lower(),
                    "status": a.get("status", ""),
                    "category": a.get("category", ""),
                    "created": a.get("alertCreationTime", "")[:10],
                    "device": a.get("computerDnsName", ""),
                    "description": a.get("description", "")[:200],
                })
            logger.info("Defender alerts: %d", len(alerts))
            return alerts
        except Exception as e:
            logger.error("Erro ao coletar alerts: %s", e)
            return []

    def _collect_incidents(self) -> list[dict]:
        """Incidentes dos últimos 30 dias. Tenta Defender API, fallback Graph."""
        since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Tenta via Graph API beta (SecurityIncident.Read.All)
        try:
            resp = requests.get(
                "https://graph.microsoft.com/beta/security/incidents",
                headers={"Authorization": f"Bearer {self.graph_token}"},
                params={"$top": 100},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            incidents = []
            for inc in result.get("value", []):
                created = inc.get("createdDateTime", "")
                if created and created < since:
                    continue
                incidents.append({
                    "id": str(inc.get("id", "")),
                    "name": inc.get("displayName", ""),
                    "severity": inc.get("severity", "").lower(),
                    "status": inc.get("status", ""),
                    "created": created[:10] if created else "",
                    "classification": inc.get("classification", ""),
                    "alerts_count": len(inc.get("alerts", [])),
                })
            logger.info("Defender incidents (Graph): %d", len(incidents))
            return incidents
        except Exception:
            pass

        # Fallback: Defender ATP API
        try:
            result = self._defender_get("/incidents", params={
                "$top": 100,
            })
            incidents = []
            for inc in result.get("value", []):
                incidents.append({
                    "id": str(inc.get("incidentId", "")),
                    "name": inc.get("incidentName", ""),
                    "severity": inc.get("severity", "").lower(),
                    "status": inc.get("status", ""),
                    "created": inc.get("createdTime", "")[:10],
                    "classification": inc.get("classification", ""),
                    "alerts_count": len(inc.get("alerts", [])),
                })
            logger.info("Defender incidents (ATP): %d", len(incidents))
            return incidents
        except Exception as e:
            logger.error("Erro ao coletar incidents: %s", e)
            return []

    def _collect_secure_score(self) -> dict:
        """Microsoft Secure Score com detalhamento por categoria."""
        try:
            # Busca control profiles para obter maxScore real por controle
            profiles = {}
            result = self._graph_get("/security/secureScoreControlProfiles", params={"$top": 500})
            for p in result.get("value", []):
                profiles[p["id"]] = p.get("maxScore", 0)

            # Busca score atual
            result = self._graph_get("/security/secureScores", params={"$top": 1})
            scores = result.get("value", [])
            if not scores:
                return {}
            s = scores[0]
            current = s.get("currentScore", 0)
            max_score = s.get("maxScore", 1)
            pct = round(current / max_score * 100, 2) if max_score > 0 else 0

            # Detalhamento por categoria com maxScore real dos profiles
            categories = {}
            for cs in s.get("controlScores", []):
                cat = cs.get("controlCategory", "Other")
                name = cs.get("controlName", "")
                ctrl_current = cs.get("score", 0)
                ctrl_max = profiles.get(name, 0)
                if ctrl_max == 0:
                    # Fallback: estima a partir do scoreInPercentage
                    sp = cs.get("scoreInPercentage", 0)
                    ctrl_max = round(ctrl_current / (sp / 100), 2) if sp > 0 and ctrl_current > 0 else ctrl_current

                if cat not in categories:
                    categories[cat] = {"current": 0.0, "max": 0.0}
                categories[cat]["current"] += ctrl_current
                categories[cat]["max"] += ctrl_max

            cat_list = []
            for cat, vals in sorted(categories.items()):
                cat_pct = round(vals["current"] / vals["max"] * 100, 2) if vals["max"] > 0 else 0
                cat_list.append({
                    "category": cat,
                    "current": round(vals["current"], 2),
                    "max": round(vals["max"], 2),
                    "pct": cat_pct,
                })

            logger.info("Secure Score: %.2f/%.2f (%.2f%%)", current, max_score, pct)
            return {
                "current": round(current, 2),
                "max": round(max_score, 2),
                "pct": pct,
                "categories": cat_list,
            }
        except Exception as e:
            logger.error("Erro ao coletar secure score: %s", e)
            return {}

    def _collect_devices(self) -> dict:
        """Inventário de dispositivos gerenciados."""
        try:
            result = self._defender_get("/machines", params={"$top": 1000})
            machines = result.get("value", [])

            devices = []
            os_counts = {}
            health_counts = {"active": 0, "inactive": 0, "no_sensor": 0}
            exposure_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
            onboarded = 0

            for m in machines:
                os_name = m.get("osPlatform", "Unknown")
                os_counts[os_name] = os_counts.get(os_name, 0) + 1

                health = m.get("healthStatus", "unknown").lower()
                if health == "active":
                    health_counts["active"] += 1
                elif health == "inactive":
                    health_counts["inactive"] += 1
                else:
                    health_counts["no_sensor"] += 1

                exposure = m.get("exposureLevel", "none").lower()
                if exposure in exposure_counts:
                    exposure_counts[exposure] += 1

                if m.get("onboardingStatus", "").lower() == "onboarded":
                    onboarded += 1

                devices.append({
                    "name": m.get("computerDnsName", ""),
                    "os": os_name,
                    "os_version": m.get("osVersion", ""),
                    "health": health,
                    "exposure": exposure,
                    "risk_score": m.get("riskScore", "none").lower(),
                    "last_seen": m.get("lastSeen", "")[:10],
                    "onboarded": m.get("onboardingStatus", "").lower() == "onboarded",
                })

            logger.info("Defender devices: %d", len(devices))
            return {
                "total": len(devices),
                "onboarded": onboarded,
                "health": health_counts,
                "exposure": exposure_counts,
                "os_distribution": os_counts,
                "devices": devices[:200],  # Limita para o JSON
            }
        except Exception as e:
            logger.error("Erro ao coletar devices: %s", e)
            return {"total": 0, "onboarded": 0, "health": {}, "exposure": {}, "os_distribution": {}, "devices": []}

    def _collect_vulnerabilities(self) -> list[dict]:
        """Top vulnerabilidades (CVEs) do ambiente."""
        try:
            result = self._defender_get("/vulnerabilities", params={
                "$top": 100,
                "$orderby": "severity desc,publishedOn desc",
            })
            vulns = []
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for v in result.get("value", []):
                sev = v.get("severity", "low").lower()
                if sev in severity_counts:
                    severity_counts[sev] += 1
                vulns.append({
                    "id": v.get("id", ""),
                    "name": v.get("name", ""),
                    "description": v.get("description", "")[:200],
                    "severity": sev,
                    "exposed_machines": v.get("exposedMachines", 0),
                    "published": v.get("publishedOn", "")[:10],
                    "cvss": v.get("cvssV3", 0),
                    "has_exploit": v.get("publicExploit", False),
                })
            logger.info("Defender vulnerabilities: %d", len(vulns))
            return vulns
        except Exception as e:
            logger.error("Erro ao coletar vulnerabilities: %s", e)
            return []

    def _collect_recommendations(self) -> list[dict]:
        """Recomendações de segurança."""
        try:
            result = self._defender_get("/recommendations", params={
                "$top": 50,
                "$orderby": "severityScore desc",
            })
            recs = []
            for r in result.get("value", []):
                recs.append({
                    "id": r.get("id", ""),
                    "name": r.get("recommendationName", ""),
                    "category": r.get("recommendationCategory", ""),
                    "severity_score": r.get("severityScore", 0),
                    "exposed_machines": r.get("exposedMachinesCount", 0),
                    "status": r.get("status", ""),
                    "remediation_type": r.get("remediationType", ""),
                    "vendor": r.get("vendor", ""),
                    "product": r.get("productName", ""),
                })
            logger.info("Defender recommendations: %d", len(recs))
            return recs
        except Exception as e:
            logger.error("Erro ao coletar recommendations: %s", e)
            return []

    @staticmethod
    def _build_summary(data: dict) -> dict:
        """Constrói resumo consolidado."""
        alerts = data.get("alerts", [])
        vulns = data.get("vulnerabilities", [])
        devices = data.get("devices", {})
        score = data.get("secure_score", {})
        incidents = data.get("incidents", [])

        alert_severity = {"high": 0, "medium": 0, "low": 0, "informational": 0}
        for a in alerts:
            sev = a.get("severity", "informational")
            if sev in alert_severity:
                alert_severity[sev] += 1

        active_alerts = len([a for a in alerts if a.get("status") != "Resolved"])
        active_incidents = len([i for i in incidents if i.get("status") != "resolved"])

        vuln_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for v in vulns:
            sev = v.get("severity", "low")
            if sev in vuln_severity:
                vuln_severity[sev] += 1

        return {
            "total_alerts": len(alerts),
            "active_alerts": active_alerts,
            "alert_severity": alert_severity,
            "total_incidents": len(incidents),
            "active_incidents": active_incidents,
            "total_devices": devices.get("total", 0),
            "onboarded_devices": devices.get("onboarded", 0),
            "device_health": devices.get("health", {}),
            "device_exposure": devices.get("exposure", {}),
            "total_vulnerabilities": len(vulns),
            "vuln_severity": vuln_severity,
            "vulns_with_exploit": len([v for v in vulns if v.get("has_exploit")]),
            "secure_score_pct": score.get("pct", 0),
            "secure_score_current": score.get("current", 0),
            "secure_score_max": score.get("max", 0),
        }
