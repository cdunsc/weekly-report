#!/usr/bin/env python3
"""
Refresh isolado do Microsoft Defender no report-data.json.
Coleta dados atualizados e substitui apenas a chave 'defender' no JSON,
sem re-executar todo o pipeline.
"""

import json
import logging
import os
import sys
import time

sys.path.insert(0, "/opt/weekly-report")

from env_loader import inject_secrets
from log_config import setup_logging

logger = logging.getLogger(__name__)

CONFIG_FILE = "/opt/weekly-report/config.yaml"
REPORT_JSON = "/opt/weekly-report/data/report-data.json"


def main():
    setup_logging()
    logger.info("=== Refresh Defender ===")

    import yaml
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    inject_secrets(config)

    if not config.get("defender", {}).get("enabled"):
        logger.info("Defender desabilitado no config, saindo.")
        return

    t0 = time.time()
    try:
        from collectors.defender_collector import DefenderCollector
        logger.info("Coletando dados do Microsoft Defender...")
        defender = DefenderCollector({
            "tenant_id": config["email"]["tenant_id"],
            "client_id": config["email"]["client_id"],
            "client_secret": config["email"]["client_secret"],
        })
        defender_data = defender.collect()
        duration = round(time.time() - t0, 1)
        logger.info("Defender: %d alerts, %d devices, %d vulns (%.1fs)",
                     len(defender_data.get("alerts", [])),
                     defender_data.get("devices", {}).get("total", 0),
                     len(defender_data.get("vulnerabilities", [])),
                     duration)
    except Exception as e:
        logger.error("Defender ERRO: %s", e)
        logger.exception("Detalhes:")
        sys.exit(1)

    # Atualiza apenas a chave 'defender' no report-data.json
    if not os.path.exists(REPORT_JSON):
        logger.error("report-data.json não encontrado: %s", REPORT_JSON)
        sys.exit(1)

    with open(REPORT_JSON) as f:
        report = json.load(f)

    report["defender"] = defender_data
    report["collector_metrics"]["defender"] = {"status": "ok", "duration_s": duration}

    with open(REPORT_JSON, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("report-data.json atualizado (defender). Concluído.")


if __name__ == "__main__":
    main()
