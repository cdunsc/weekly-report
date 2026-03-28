"""
Configuração centralizada de logging para o relatório semanal.
"""

import logging
import logging.handlers
import os

LOG_FILE = "/opt/weekly-report/data/weekly-report.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level=logging.INFO):
    """Configura handlers de arquivo (rotativo) e console."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Evita duplicar handlers se chamado mais de uma vez
    if root.handlers:
        return

    formatter = logging.Formatter(LOG_FORMAT)

    # RotatingFileHandler: 5 MB x 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)
