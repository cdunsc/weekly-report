#!/usr/bin/env python3
"""
Servidor Flask do Dashboard.
Gerencia autenticação (login/logout/reset), troca de senha obrigatória
no primeiro acesso e serve o dashboard protegido.

Roda em 127.0.0.1:8080, proxy via nginx.
"""

import json
import logging
import os
import secrets
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_from_directory,
    jsonify,
    url_for,
)

import yaml

from env_loader import inject_secrets
from auth import (
    verify_user,
    get_user,
    change_password,
    get_user_by_email,
    create_reset_token,
    verify_reset_token,
    consume_reset_token,
    validate_password,
)

CONFIG_FILE = "/opt/weekly-report/config.yaml"


def _load_config() -> dict:
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    return inject_secrets(config)


def _load_secret_key() -> str:
    try:
        cfg = _load_config()
        return cfg.get("dashboard", {}).get("secret_key", "")
    except Exception:
        return ""


app = Flask(
    __name__,
    template_folder="/opt/weekly-report/report/templates",
)
app.secret_key = (
    _load_secret_key()
    or os.environ.get("FLASK_SECRET_KEY")
    or secrets.token_hex(32)
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 14400  # 4h

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

DASHBOARD_DIR = "/var/www/html/dashboard"
DATA_FILE = "/opt/weekly-report/data/golden_cloud.json"
OTRS_CACHE_FILE = "/opt/weekly-report/data/otrs_cache.json"
STATIC_DIR = "/opt/weekly-report/static"


# --- Auth helpers ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        # Se precisa trocar senha, redireciona (exceto se já está na rota de troca)
        user_data = get_user(session["user"])
        if user_data and user_data["must_change_password"]:
            return redirect(url_for("change_password_page"))
        return f(*args, **kwargs)
    return decorated


def _send_reset_email(to_email: str, username: str, reset_url: str):
    """Envia e-mail de reset de senha via Microsoft Graph API."""
    try:
        cfg = _load_config()
        email_cfg = cfg["email"]

        from delivery.email_sender import EmailSender
        sender = EmailSender(email_cfg)

        html_body = f"""
        <div style="font-family: 'Segoe UI', sans-serif; max-width: 500px; margin: 0 auto;
                    background: #1e293b; color: #e2e8f0; padding: 32px; border-radius: 12px;">
            <h2 style="color: #3b82f6; margin-bottom: 16px;">Surf Telecom - Reset de Senha</h2>
            <p>Ola <strong>{username}</strong>,</p>
            <p>Recebemos uma solicitacao para redefinir sua senha.</p>
            <p style="margin: 24px 0;">
                <a href="{reset_url}"
                   style="background: #3b82f6; color: #fff; padding: 14px 28px;
                          border-radius: 10px; text-decoration: none; font-weight: 600;
                          display: inline-block;">
                    Redefinir Minha Senha
                </a>
            </p>
            <p style="color: #94a3b8; font-size: 0.85rem;">
                Este link expira em <strong>1 hora</strong>.<br>
                Se voce nao solicitou, ignore este e-mail.
            </p>
        </div>
        """

        # Envia direto usando Graph API (reutilizando o sender)
        sender.to_addrs = [to_email]
        sender.send(
            subject="Surf Telecom - Redefinir Senha",
            html_body=html_body,
        )
        logger.info("E-mail de reset enviado para %s", to_email)
        return True
    except Exception as e:
        logger.error("Erro ao enviar e-mail de reset: %s", e)
        return False


# --- Routes ---

@app.route("/dashboard/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route("/dashboard/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if session.get("user"):
        user_data = get_user(session["user"])
        if user_data and user_data["must_change_password"]:
            return redirect(url_for("change_password_page"))
        return redirect(url_for("dashboard"))

    error = None
    success = request.args.get("success")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if verify_user(username, password):
            session.permanent = True
            session["user"] = username
            # Verifica se precisa trocar senha
            user_data = get_user(username)
            if user_data and user_data["must_change_password"]:
                return redirect(url_for("change_password_page"))
            return redirect(url_for("dashboard"))
        else:
            error = "Usuario ou senha invalidos."

    return render_template("login.html", error=error, success=success)


@app.route("/dashboard/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard/change-password", methods=["GET", "POST"])
def change_password_page():
    if not session.get("user"):
        return redirect(url_for("login"))

    username = session["user"]
    user_data = get_user(username)
    first_login = user_data and user_data["must_change_password"]
    error = None

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        # No primeiro login, não exige senha atual
        if not first_login and not verify_user(username, current_password):
            error = "Senha atual incorreta."
        elif new_password != confirm_password:
            error = "As senhas nao conferem."
        else:
            pwd_error = validate_password(new_password)
            if pwd_error:
                error = pwd_error
            else:
                change_password(username, new_password)
                return redirect(url_for("dashboard"))

    return render_template(
        "change_password.html",
        user=username,
        first_login=first_login,
        error=error,
    )


@app.route("/dashboard/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def forgot_password():
    error = None
    success = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_user_by_email(email)

        if user:
            token = create_reset_token(user["username"])
            # Monta URL de reset usando base_url do config
            try:
                cfg = _load_config()
                base = cfg["dashboard"]["base_url"].rstrip("/")
            except Exception:
                base = request.host_url.rstrip("/") + "/dashboard"
            reset_url = f"{base}/reset-password/{token}"

            if _send_reset_email(email, user["username"], reset_url):
                success = f"Link de recuperacao enviado para {email}."
            else:
                error = "Erro ao enviar e-mail. Tente novamente."
        else:
            # Mensagem genérica por segurança
            success = f"Se o e-mail estiver cadastrado, um link sera enviado."

    return render_template(
        "forgot_password.html", error=error, success=success
    )


@app.route("/dashboard/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    username = verify_reset_token(token)
    error = None

    if not username:
        return render_template(
            "reset_password.html", expired=True, user="", token=token, error=None
        )

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password != confirm_password:
            error = "As senhas nao conferem."
        else:
            pwd_error = validate_password(new_password)
            if pwd_error:
                error = pwd_error
            else:
                change_password(username, new_password)
                consume_reset_token(token)
                return redirect(url_for("login", success="Senha redefinida com sucesso."))

    return render_template(
        "reset_password.html",
        expired=False,
        user=username,
        token=token,
        error=error,
    )


@app.route("/dashboard/health")
def health():
    """Health check — verifica se o serviço está rodando e dados atualizados."""
    checks = {"status": "ok", "service": "weekly-report-dashboard"}

    # Verifica se dashboard existe
    index_path = os.path.join(DASHBOARD_DIR, "index.html")
    if os.path.exists(index_path):
        mtime = os.path.getmtime(index_path)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        checks["dashboard_age_hours"] = round(age_hours, 1)
        checks["dashboard_stale"] = age_hours > 168  # >7 dias
    else:
        checks["dashboard_age_hours"] = None
        checks["dashboard_stale"] = True

    if checks.get("dashboard_stale"):
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "ok" else 503
    return jsonify(checks), status_code


@app.route("/dashboard/")
@app.route("/dashboard")
@login_required
def dashboard():
    """Serve o dashboard HTML gerado."""
    index_path = os.path.join(DASHBOARD_DIR, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(DASHBOARD_DIR, "index.html")
    return (
        "<h1>Dashboard ainda nao foi gerado.</h1><p>Execute main.py primeiro.</p>",
        404,
    )


# --- Chamados por Serviço ---

@app.route("/dashboard/chamados/<path:service_filter>")
@login_required
def chamados_por_servico(service_filter):
    """Página de chamados filtrados por categoria de serviço."""
    # Carrega cache OTRS
    tickets = []
    queue_name = request.args.get("fila", "TI")
    if os.path.exists(OTRS_CACHE_FILE):
        with open(OTRS_CACHE_FILE) as f:
            otrs_data = json.load(f)
        for q in otrs_data:
            if q.get("queue_name") == queue_name:
                tickets = q.get("tickets", [])
                break

    # Filtra por serviço (o path usa --- no lugar de ::)
    service_name = service_filter.replace("---", "::")
    if service_name in ("Sem Serviço", "Sem Servico"):
        filtered = [t for t in tickets if not t.get("service", "").strip()]
        service_name = "Sem Serviço"
    else:
        filtered = [t for t in tickets if t.get("service", "") == service_name]

    # Separa abertos e fechados
    closed_states = {
        "Fechado com êxito", "Fechado sem êxito", "fechado",
        "fechado com êxito", "fechado sem êxito",
        "fechado com solução de contorno", "Encerrado",
        "Resolvido", "Indevido",
    }
    abertos = [t for t in filtered if t.get("state", "") not in closed_states]
    fechados = [t for t in filtered if t.get("state", "") in closed_states]

    otrs_panel_url = _load_config().get("otrs", {}).get("panel_url", "https://ticket.surf.com.br")

    return render_template(
        "chamados_servico.html",
        service_name=service_name,
        queue_name=queue_name,
        tickets=filtered,
        abertos=abertos,
        fechados=fechados,
        total=len(filtered),
        otrs_panel_url=otrs_panel_url,
    )


# --- Chamados por Solicitante ---

@app.route("/dashboard/solicitante/<path:customer_filter>")
@login_required
def chamados_por_solicitante(customer_filter):
    """Página de chamados filtrados por solicitante."""
    tickets = []
    queue_name = request.args.get("fila", "TI")
    if os.path.exists(OTRS_CACHE_FILE):
        with open(OTRS_CACHE_FILE) as f:
            otrs_data = json.load(f)
        for q in otrs_data:
            if q.get("queue_name") == queue_name:
                tickets = q.get("tickets", [])
                break

    customer_name = customer_filter
    if customer_name in ("N/A", "Abertura Automática"):
        filtered = [t for t in tickets if not t.get("customer", "").strip()]
        customer_name = "Abertura Automática"
    else:
        filtered = [t for t in tickets if t.get("customer", "").strip() == customer_name]

    closed_states = {
        "Fechado com êxito", "Fechado sem êxito", "fechado",
        "fechado com êxito", "fechado sem êxito",
        "fechado com solução de contorno", "Encerrado",
        "Resolvido", "Indevido",
    }
    abertos = [t for t in filtered if t.get("state", "") not in closed_states]
    fechados = [t for t in filtered if t.get("state", "") in closed_states]

    otrs_panel_url = _load_config().get("otrs", {}).get("panel_url", "https://ticket.surf.com.br")

    return render_template(
        "chamados_solicitante.html",
        customer_name=customer_name,
        queue_name=queue_name,
        tickets=filtered,
        abertos=abertos,
        fechados=fechados,
        total=len(filtered),
        otrs_panel_url=otrs_panel_url,
    )


# --- Chamados por Atendente ---

@app.route("/dashboard/atendente/<path:owner_filter>")
@login_required
def chamados_por_atendente(owner_filter):
    """Página de chamados filtrados por atendente."""
    tickets = []
    queue_name = request.args.get("fila", "TI")
    if os.path.exists(OTRS_CACHE_FILE):
        with open(OTRS_CACHE_FILE) as f:
            otrs_data = json.load(f)
        for q in otrs_data:
            if q.get("queue_name") == queue_name:
                tickets = q.get("tickets", [])
                break

    owner_name = owner_filter
    if owner_name == "Não Atribuído":
        filtered = [t for t in tickets if not t.get("owner", "").strip()]
    else:
        filtered = [t for t in tickets if t.get("owner", "").strip() == owner_name]

    closed_states = {
        "Fechado com êxito", "Fechado sem êxito", "fechado",
        "fechado com êxito", "fechado sem êxito",
        "fechado com solução de contorno", "Encerrado",
        "Resolvido", "Indevido",
    }
    abertos = [t for t in filtered if t.get("state", "") not in closed_states]
    fechados = [t for t in filtered if t.get("state", "") in closed_states]

    otrs_panel_url = _load_config().get("otrs", {}).get("panel_url", "https://ticket.surf.com.br")

    return render_template(
        "chamados_atendente.html",
        owner_name=owner_name,
        queue_name=queue_name,
        tickets=filtered,
        abertos=abertos,
        fechados=fechados,
        total=len(filtered),
        otrs_panel_url=otrs_panel_url,
    )


# --- Golden Cloud API ---

@app.route("/dashboard/api/golden-cloud", methods=["POST"])
@login_required
def golden_cloud_api():
    try:
        data = request.get_json(force=True)
        total_cost = float(data.get("total_cost", 0))
        currency = data.get("currency", "BRL")
        details = data.get("details", [])

        save_data = {
            "updated_at": datetime.now().isoformat(),
            "total_cost": total_cost,
            "currency": currency,
            "details": details,
        }

        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump(save_data, f, indent=2)

        return jsonify({"status": "ok", "saved": save_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/dashboard/api/golden-cloud", methods=["OPTIONS"])
def golden_cloud_options():
    resp = app.make_default_options_response()
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


def main():
    app.run(host="127.0.0.1", port=8080, debug=False)


if __name__ == "__main__":
    main()
