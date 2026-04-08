"""
Carrega variáveis de ambiente do arquivo .env e injeta os segredos
no dicionário de configuração carregado do config.yaml.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega .env uma vez ao importar o módulo
_ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(_ENV_FILE)


def inject_secrets(config: dict) -> dict:
    """
    Lê variáveis de ambiente e injeta no config dict.
    Se a variável não estiver definida, mantém o valor já presente no config
    (backward compat com config.yaml que ainda contenha o valor).
    """

    def _get(env_key: str, current_value: str) -> str:
        return os.environ.get(env_key) or current_value

    # OTRS
    otrs = config.setdefault("otrs", {})
    otrs["username"] = _get("OTRS_USERNAME", otrs.get("username", ""))
    otrs["password"] = _get("OTRS_PASSWORD", otrs.get("password", ""))

    # Golden Cloud
    gc = config.setdefault("golden_cloud", {})
    gc["username"] = _get("GOLDEN_CLOUD_USERNAME", gc.get("username", ""))
    gc["password"] = _get("GOLDEN_CLOUD_PASSWORD", gc.get("password", ""))

    # E-mail
    email = config.setdefault("email", {})
    email["tenant_id"] = _get("EMAIL_TENANT_ID", email.get("tenant_id", ""))
    email["client_id"] = _get("EMAIL_CLIENT_ID", email.get("client_id", ""))
    email["client_secret"] = _get("EMAIL_CLIENT_SECRET", email.get("client_secret", ""))
    email["user_principal_name"] = _get(
        "EMAIL_USER_PRINCIPAL_NAME", email.get("user_principal_name", "")
    )

    # Monday.com
    monday = config.setdefault("monday", {})
    monday["api_token"] = _get("MONDAY_API_TOKEN", monday.get("api_token", ""))

    # Teams
    teams = config.setdefault("teams", {})
    teams["webhook_url"] = _get("TEAMS_WEBHOOK_URL", teams.get("webhook_url", ""))

    # SPEC
    spec = config.setdefault("spec", {})
    spec["username"] = _get("SPEC_USERNAME", spec.get("username", ""))
    spec["password"] = _get("SPEC_PASSWORD", spec.get("password", ""))

    # Dashboard
    dashboard = config.setdefault("dashboard", {})
    dashboard["secret_key"] = _get(
        "DASHBOARD_SECRET_KEY", dashboard.get("secret_key", "")
    )

    return config
