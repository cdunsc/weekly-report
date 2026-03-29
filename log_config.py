"""
Configuração centralizada de logging para o relatório semanal.
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime

LOG_FILE = "/opt/weekly-report/data/weekly-report.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class JsonFormatter(logging.Formatter):
    """Formatter que produz saída estruturada em JSON (uma linha por log)."""

    def format(self, record):
        """Formata um LogRecord como uma linha JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }

        # Inclui informações de exceção se presentes
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(level=logging.INFO):
    """Configura handlers de arquivo (rotativo) com JSON estruturado e console legível."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Evita duplicar handlers se chamado mais de uma vez
    if root.handlers:
        return

    # RotatingFileHandler: 5 MB x 3 backups com JSON estruturado
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)

    # Console handler com formato legível
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(console_handler)
