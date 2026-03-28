"""
Envio de relatório por e-mail via Microsoft Graph API (OAuth2).
"""

import json
import logging
import msal
import urllib.request

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, config: dict):
        self.from_addr = config["from"]
        self.to_addrs = config["to"]
        self.tenant_id = config["tenant_id"]
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.user_principal_name = config["user_principal_name"]

    def _get_token(self) -> str:
        """Obtém token OAuth2 via client credentials."""
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"Falha ao obter token: {result.get('error_description', result)}")
        return result["access_token"]

    def send(self, subject: str, html_body: str):
        """
        Envia e-mail HTML via Microsoft Graph API.

        Args:
            subject: Assunto do e-mail
            html_body: Corpo em HTML
        """
        token = self._get_token()

        recipients = [
            {"emailAddress": {"address": addr}} for addr in self.to_addrs
        ]

        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": html_body,
                },
                "toRecipients": recipients,
            },
            "saveToSentItems": "true",
        }

        url = f"https://graph.microsoft.com/v1.0/users/{self.user_principal_name}/sendMail"
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")

        try:
            urllib.request.urlopen(req)
            logger.info("Relatório enviado para %s", ', '.join(self.to_addrs))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Graph API erro {e.code}: {body}")
