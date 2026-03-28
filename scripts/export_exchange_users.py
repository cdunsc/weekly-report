#!/usr/bin/env python3
"""
Exporta usuários do Exchange Online (Microsoft 365) via Graph API.
Campos: Nome, E-mail, Data de Criação, Última Atividade (mailbox).

Requisitos no Azure AD (App Registration):
  - API permissions (Application): User.Read.All, Reports.Read.All
  - Admin consent concedido

Uso:
    python export_exchange_users.py              # Exibe no terminal
    python export_exchange_users.py --csv        # Salva em CSV
    python export_exchange_users.py --csv -o usuarios.csv  # CSV com nome customizado
"""

import argparse
import csv
import io
from datetime import datetime

import requests
import yaml


CONFIG_FILE = "/opt/weekly-report/config.yaml"


def load_config():
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=15,
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Falha na autenticação: {data.get('error_description', data)}")
    return data["access_token"]


def _fetch_mailbox_activity(token: str) -> dict:
    """Busca relatório de atividade de mailbox (últimos 90 dias).
    Retorna dict: email_lower -> last_activity_date (str)."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        "https://graph.microsoft.com/v1.0/reports/getMailboxUsageDetail(period='D90')",
        headers=headers,
        timeout=60,
    )
    activity = {}
    if resp.status_code == 200:
        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            upn = (row.get("User Principal Name") or "").strip().lower()
            last = row.get("Last Activity Date") or ""
            if upn:
                activity[upn] = last
        print(f"[REPORT] Atividade de mailbox: {len(activity)} registros")
    else:
        print(f"[REPORT] Não foi possível obter relatório de mailbox (status {resp.status_code})")
    return activity


def fetch_all_users(token: str) -> list[dict]:
    """Busca todos os usuários com paginação automática."""
    # Busca atividade de mailbox para cruzar com último login
    activity = _fetch_mailbox_activity(token)

    users = []
    fields = "displayName,mail,userPrincipalName,createdDateTime,accountEnabled,refreshTokensValidFromDateTime"
    url = (
        f"https://graph.microsoft.com/beta/users"
        f"?$select={fields}"
        f"&$top=999"
    )
    headers = {"Authorization": f"Bearer {token}"}

    today = datetime.now().date()

    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for u in data.get("value", []):
            email = u.get("mail") or u.get("userPrincipalName") or ""
            if not email or "#EXT#" in email:
                continue

            upn = (u.get("userPrincipalName") or "").lower()
            last_activity_raw = activity.get(upn, "")
            last_activity = _format_date_short(last_activity_raw)

            # Determina status de atividade e data de desativação
            disabled_date = ""
            if not u.get("accountEnabled"):
                status = "Desativado"
                disabled_date = _format_date(u.get("refreshTokensValidFromDateTime"))
            elif not last_activity_raw:
                status = "Sem atividade"
            else:
                try:
                    last_dt = datetime.strptime(last_activity_raw.strip(), "%Y-%m-%d").date()
                    days_inactive = (today - last_dt).days
                    if days_inactive <= 90:
                        status = "Ativo"
                    else:
                        status = f"Inativo ({days_inactive} dias)"
                except (ValueError, TypeError):
                    status = "Sem atividade"

            users.append({
                "nome": u.get("displayName", ""),
                "email": email,
                "criado_em": _format_date(u.get("createdDateTime")),
                "ultima_atividade": last_activity,
                "status": status,
                "desativado_em": disabled_date,
            })

        url = data.get("@odata.nextLink")

    users.sort(key=lambda x: x["nome"].lower())
    return users


def _format_date(iso_str: str | None) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return iso_str


def _format_date_short(date_str: str | None) -> str:
    """Formata data YYYY-MM-DD para DD/MM/YYYY."""
    if not date_str:
        return "—"
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return date_str


def print_table(users: list[dict]):
    if not users:
        print("Nenhum usuário encontrado.")
        return

    cols = {"nome": "Nome", "email": "E-mail", "criado_em": "Criado em", "ultima_atividade": "Última Atividade", "status": "Status", "desativado_em": "Desativado em"}
    widths = {}
    for key, header in cols.items():
        widths[key] = max(len(header), max((len(u[key]) for u in users), default=0))

    header_line = "  ".join(h.ljust(widths[k]) for k, h in cols.items())
    sep = "  ".join("-" * widths[k] for k in cols)

    print(f"\nTotal: {len(users)} usuários ativos\n")
    print(header_line)
    print(sep)
    for u in users:
        print("  ".join(u[k].ljust(widths[k]) for k in cols))


def save_csv(users: list[dict], filename: str):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["nome", "email", "criado_em", "ultima_atividade", "status", "desativado_em"],
                                delimiter=";")
        writer.writeheader()
        writer.writerows(users)
    print(f"CSV salvo: {filename} ({len(users)} usuários)")


def main():
    parser = argparse.ArgumentParser(description="Exporta usuários do Exchange Online")
    parser.add_argument("--csv", action="store_true", help="Salva em CSV")
    parser.add_argument("-o", "--output", default="exchange_users.csv", help="Nome do arquivo CSV")
    args = parser.parse_args()

    config = load_config()
    email_cfg = config["email"]

    print("[AUTH] Autenticando no Microsoft Graph...")
    token = get_token(email_cfg["tenant_id"], email_cfg["client_id"], email_cfg["client_secret"])

    print("[GRAPH] Buscando usuários...")
    users = fetch_all_users(token)

    if args.csv:
        save_csv(users, args.output)
    else:
        print_table(users)


if __name__ == "__main__":
    main()
