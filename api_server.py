#!/usr/bin/env python3
"""
Servidor Flask do Dashboard.
Gerencia autenticação (login/logout/reset), troca de senha obrigatória
no primeiro acesso e serve o dashboard protegido.

Roda em 127.0.0.1:8080, proxy via nginx.
"""

import csv
import json
import logging
import os
import secrets
import subprocess
import tempfile
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
from log_config import setup_logging
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
from collectors.otrs_collector import CLOSED_STATES

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
    """Envia e-mail de reset de senha via shared email helper."""
    import sys
    sys.path.insert(0, "/opt/shared-auth")
    from email_helper import send_reset_email
    return send_reset_email(to_email, username, reset_url)


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
        "<h1>Dashboard ainda não foi gerado.</h1><p>Execute o build do frontend.</p>",
        404,
    )


@app.route("/dashboard/assets/<path:filename>")
@login_required
def dashboard_assets(filename):
    """Serve assets do React build (JS, CSS, imagens)."""
    assets_dir = os.path.join(DASHBOARD_DIR, "assets")
    return send_from_directory(assets_dir, filename)


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
    abertos = [t for t in filtered if t.get("state", "") not in CLOSED_STATES]
    fechados = [t for t in filtered if t.get("state", "") in CLOSED_STATES]

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

    abertos = [t for t in filtered if t.get("state", "") not in CLOSED_STATES]
    fechados = [t for t in filtered if t.get("state", "") in CLOSED_STATES]

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

    abertos = [t for t in filtered if t.get("state", "") not in CLOSED_STATES]
    fechados = [t for t in filtered if t.get("state", "") in CLOSED_STATES]

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
        logger.error("Erro na API golden-cloud: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/dashboard/api/golden-cloud", methods=["OPTIONS"])
def golden_cloud_options():
    resp = app.make_default_options_response()
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


REPORT_DATA_FILE = "/opt/weekly-report/data/report-data.json"


@app.route("/dashboard/api/report-data")
@login_required
def report_data_api():
    """Serve dados do relatório para o frontend React."""
    if not os.path.exists(REPORT_DATA_FILE):
        return jsonify({"error": "Dados ainda não gerados. Execute main.py primeiro."}), 404
    with open(REPORT_DATA_FILE) as f:
        data = json.load(f)
    return jsonify(data)


# --- SPEC User Creation API ---

SPEC_SCRIPT = "/home/ubuntu/criar_usuario_spec.py"
SPEC_VERIFY_SCRIPT = "/home/ubuntu/verificar_usuario_spec.py"


@app.route("/dashboard/api/spec-users", methods=["POST"])
@login_required
def spec_users_api():
    """
    Cria usuários na plataforma SPEC.

    Espera JSON:
      { "users": [ {"nome": "...", "email": "...", "mvno": "..."}, ... ] }

    Campos obrigatórios por usuário: nome, email.
    Campo mvno é opcional (padrão: DESKTOP).

    Credenciais SPEC são lidas do config.yaml / .env (nunca do request).
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"status": "error", "message": "JSON inválido."}), 400

    users = data.get("users")
    if not users or not isinstance(users, list):
        return jsonify({
            "status": "error",
            "message": "Campo 'users' é obrigatório e deve ser uma lista.",
        }), 400

    # Validar cada usuário
    validated = []
    errors = []
    for i, u in enumerate(users):
        nome = (u.get("nome") or "").strip()
        email = (u.get("email") or "").strip()
        mvno = (u.get("mvno") or "DESKTOP").strip()

        if not nome or not email:
            errors.append({
                "index": i,
                "nome": nome,
                "email": email,
                "error": "Campos 'nome' e 'email' são obrigatórios.",
            })
            continue

        validated.append({"nome": nome, "email": email, "mvno": mvno})

    if not validated:
        return jsonify({
            "status": "error",
            "message": "Nenhum usuário válido na lista.",
            "validation_errors": errors,
        }), 400

    # Carregar credenciais SPEC do config
    try:
        cfg = _load_config()
        spec_cfg = cfg.get("spec", {})
        spec_user = spec_cfg.get("username", "")
        spec_pass = spec_cfg.get("password", "")
    except Exception as e:
        logger.error("Erro ao carregar config SPEC: %s", e)
        return jsonify({
            "status": "error",
            "message": "Erro ao carregar configuração SPEC.",
        }), 500

    if not spec_user or not spec_pass:
        return jsonify({
            "status": "error",
            "message": "Credenciais SPEC não configuradas. "
                       "Defina SPEC_USERNAME e SPEC_PASSWORD no .env.",
        }), 500

    # Verificar se o script existe
    if not os.path.isfile(SPEC_SCRIPT):
        return jsonify({
            "status": "error",
            "message": f"Script não encontrado: {SPEC_SCRIPT}",
        }), 500

    # Gravar CSV temporário
    tmp_csv = None
    try:
        tmp_csv = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="spec_users_",
            dir="/tmp",
            delete=False,
            newline="",
            encoding="utf-8",
        )
        writer = csv.DictWriter(tmp_csv, fieldnames=["nome", "email", "mvno"])
        writer.writeheader()
        for u in validated:
            writer.writerow(u)
        tmp_csv.close()

        # Executar script
        cmd = [
            "python3", SPEC_SCRIPT,
            "--usuario", spec_user,
            "--senha", spec_pass,
            "--csv", tmp_csv.name,
        ]

        logger.info(
            "Executando criação SPEC para %d usuário(s) (por %s)",
            len(validated),
            session.get("user"),
        )

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        output_lines = (result.stdout or "").strip().splitlines()
        stderr_lines = (result.stderr or "").strip().splitlines()

        # Interpretar resultados por usuário a partir do stdout
        user_results = []
        for u in validated:
            # Procurar linhas relevantes para este email no output
            user_output = [
                line for line in output_lines
                if u["email"].lower() in line.lower() or u["nome"].lower() in line.lower()
            ]
            # Determinar sucesso/falha
            combined = " ".join(user_output).upper()
            if "[CONCLUIDO]" in combined or "CRIADO E CONFIGURADO" in combined:
                status = "success"
            elif "[ERRO]" in combined:
                status = "error"
            elif any("[OK]" in line for line in user_output):
                status = "partial"
            else:
                status = "unknown"

            user_results.append({
                "nome": u["nome"],
                "email": u["email"],
                "mvno": u["mvno"],
                "status": status,
                "output": user_output,
            })

        # Resumo
        total_success = sum(1 for r in user_results if r["status"] == "success")
        total_error = sum(1 for r in user_results if r["status"] == "error")

        response = {
            "status": "ok" if result.returncode == 0 else "error",
            "summary": {
                "total": len(validated),
                "success": total_success,
                "errors": total_error,
                "other": len(validated) - total_success - total_error,
            },
            "results": user_results,
            "script_exit_code": result.returncode,
            "raw_output": output_lines,
        }

        if stderr_lines:
            response["stderr"] = stderr_lines

        if errors:
            response["validation_errors"] = errors

        status_code = 200 if result.returncode == 0 else 207
        return jsonify(response), status_code

    except subprocess.TimeoutExpired:
        logger.error("Script SPEC excedeu timeout de 10 minutos")
        return jsonify({
            "status": "error",
            "message": "Timeout: o script excedeu o limite de 10 minutos.",
        }), 504

    except Exception as e:
        logger.error("Erro ao executar script SPEC: %s", e)
        return jsonify({
            "status": "error",
            "message": f"Erro interno: {e}",
        }), 500

    finally:
        if tmp_csv and os.path.exists(tmp_csv.name):
            try:
                os.unlink(tmp_csv.name)
            except OSError:
                pass


@app.route("/dashboard/api/spec-users/verify", methods=["POST"])
@login_required
def spec_users_verify_api():
    """
    Verifica se usuários existem na plataforma SPEC e se a MVNO está ativa.

    Espera JSON:
      { "users": [ {"email": "..."}, ... ], "mvno": "SKY" }
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"status": "error", "message": "JSON inválido."}), 400

    users = data.get("users")
    mvno = (data.get("mvno") or "DESKTOP").strip()

    if not users or not isinstance(users, list):
        return jsonify({
            "status": "error",
            "message": "Campo 'users' é obrigatório e deve ser uma lista.",
        }), 400

    emails = []
    for u in users:
        email = (u.get("email") or "").strip()
        if email:
            emails.append(email)

    if not emails:
        return jsonify({
            "status": "error",
            "message": "Nenhum email válido na lista.",
        }), 400

    # Carregar credenciais SPEC
    try:
        cfg = _load_config()
        spec_cfg = cfg.get("spec", {})
        spec_user = spec_cfg.get("username", "")
        spec_pass = spec_cfg.get("password", "")
    except Exception as e:
        logger.error("Erro ao carregar config SPEC: %s", e)
        return jsonify({
            "status": "error",
            "message": "Erro ao carregar configuração SPEC.",
        }), 500

    if not spec_user or not spec_pass:
        return jsonify({
            "status": "error",
            "message": "Credenciais SPEC não configuradas.",
        }), 500

    if not os.path.isfile(SPEC_VERIFY_SCRIPT):
        return jsonify({
            "status": "error",
            "message": f"Script não encontrado: {SPEC_VERIFY_SCRIPT}",
        }), 500

    # Gravar CSV temporário
    tmp_csv = None
    try:
        tmp_csv = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="spec_verify_",
            dir="/tmp",
            delete=False,
            newline="",
            encoding="utf-8",
        )
        writer = csv.DictWriter(tmp_csv, fieldnames=["email"])
        writer.writeheader()
        for email in emails:
            writer.writerow({"email": email})
        tmp_csv.close()

        cmd = [
            "python3", SPEC_VERIFY_SCRIPT,
            "--usuario", spec_user,
            "--senha", spec_pass,
            "--csv", tmp_csv.name,
            "--mvno", mvno,
        ]

        logger.info(
            "Verificando %d usuário(s) SPEC (MVNO: %s, por %s)",
            len(emails), mvno, session.get("user"),
        )

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        output_lines = (result.stdout or "").strip().splitlines()

        # Extrair JSON de resultados
        json_results = []
        for line in output_lines:
            if line.startswith("[JSON_RESULTS]"):
                try:
                    json_results = json.loads(line[len("[JSON_RESULTS]"):])
                except json.JSONDecodeError:
                    pass

        # Se não encontrou JSON, parse das linhas [RESULTADO]
        if not json_results:
            for line in output_lines:
                if "[RESULTADO]" in line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        email_part = parts[0].replace("[RESULTADO]", "").strip()
                        exists_part = "exists=true" in parts[1]
                        mvno_part = "mvno_ok=true" in parts[2]
                        details = parts[3].strip() if len(parts) > 3 else ""
                        json_results.append({
                            "email": email_part,
                            "exists": exists_part,
                            "mvno_ok": mvno_part,
                            "details": details,
                        })

        total = len(json_results)
        ok = sum(1 for r in json_results if r.get("exists") and r.get("mvno_ok"))
        no_mvno = sum(1 for r in json_results if r.get("exists") and not r.get("mvno_ok"))
        not_found = sum(1 for r in json_results if not r.get("exists"))

        return jsonify({
            "status": "ok",
            "mvno": mvno,
            "summary": {
                "total": total,
                "ok": ok,
                "no_mvno": no_mvno,
                "not_found": not_found,
            },
            "results": json_results,
        }), 200

    except subprocess.TimeoutExpired:
        logger.error("Script verificação SPEC excedeu timeout")
        return jsonify({
            "status": "error",
            "message": "Timeout: verificação excedeu o limite de 10 minutos.",
        }), 504

    except Exception as e:
        logger.error("Erro ao verificar SPEC: %s", e)
        return jsonify({
            "status": "error",
            "message": f"Erro interno: {e}",
        }), 500

    finally:
        if tmp_csv and os.path.exists(tmp_csv.name):
            try:
                os.unlink(tmp_csv.name)
            except OSError:
                pass


def main():
    setup_logging()
    app.run(host="127.0.0.1", port=8080, debug=False)


if __name__ == "__main__":
    main()
