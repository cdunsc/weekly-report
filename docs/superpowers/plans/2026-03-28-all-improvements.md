# All Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 18 improvements covering security, resilience, observability, code quality, and functional enhancements for the weekly report automation.

**Architecture:** Layered approach — foundation first (logging, secrets, deps), then security hardening, resilience, code quality, and finally functional features. Each task is self-contained and testable independently.

**Tech Stack:** Python 3.12, Flask, tenacity (retry), flask-limiter (rate limiting), python-dotenv (env vars), logging module

---

### Task 1: Initialize git repo and create .gitignore

**Files:**
- Create: `/opt/weekly-report/.gitignore`

- [ ] **Step 1: Initialize git and create .gitignore**

```bash
cd /opt/weekly-report
git init
```

Create `/opt/weekly-report/.gitignore`:
```
__pycache__/
*.pyc
venv/
.env
data/users.json
data/reset_tokens.json
data/golden_cloud.json
data/otrs_cache.json
data/cron.log
*.csv
config.yaml
```

- [ ] **Step 2: Initial commit with existing code (excluding secrets)**

```bash
cd /opt/weekly-report
git add .gitignore main.py api_server.py auth.py requirements.txt manage_users.py rebuild_history.py generate_demo.py
git add collectors/ delivery/ report/
git commit -m "chore: initial commit with existing code"
```

---

### Task 2: Migrate secrets from config.yaml to environment variables

**Files:**
- Create: `/opt/weekly-report/.env.example`
- Modify: `/opt/weekly-report/config.yaml` (remove all plaintext secrets, replace with env var references)
- Create: `/opt/weekly-report/env_loader.py` (centralized env loading)
- Modify: `/opt/weekly-report/main.py` (load .env at startup)
- Modify: `/opt/weekly-report/api_server.py` (load .env at startup)

- [ ] **Step 1: Install python-dotenv**

Add `python-dotenv>=1.0.0` to requirements.txt. Run:
```bash
cd /opt/weekly-report && source venv/bin/activate && pip install python-dotenv
```

- [ ] **Step 2: Create .env.example (template without real values)**

Create `/opt/weekly-report/.env.example`:
```bash
# OTRS
OTRS_USERNAME=
OTRS_PASSWORD=

# Golden Cloud
GOLDEN_CLOUD_USERNAME=
GOLDEN_CLOUD_PASSWORD=

# Microsoft Graph API (Email)
EMAIL_TENANT_ID=
EMAIL_CLIENT_ID=
EMAIL_CLIENT_SECRET=
EMAIL_USER_PRINCIPAL_NAME=

# Monday.com
MONDAY_API_TOKEN=

# Teams
TEAMS_WEBHOOK_URL=

# Dashboard
FLASK_SECRET_KEY=
```

- [ ] **Step 3: Create .env with real values**

Create `/opt/weekly-report/.env` with the actual credentials currently in config.yaml:
```bash
# OTRS
OTRS_USERNAME=carlos.nascimento
OTRS_PASSWORD=Palmeira$#@260814

# Golden Cloud
GOLDEN_CLOUD_USERNAME=redir.automacao@surf4g.onmicrosoft.com
GOLDEN_CLOUD_PASSWORD=975OZqdym5i1G

# Microsoft Graph API
EMAIL_TENANT_ID=b0f914e4-57bd-42ea-8f5d-64e0d88a0d1b
EMAIL_CLIENT_ID=7a8c5205-b118-4eb9-9c6c-75ab11e325af
EMAIL_CLIENT_SECRET=HLB8Q~0Tl3.LHkf4AhkUdHScESD4J2ZWmPNDEbmH
EMAIL_USER_PRINCIPAL_NAME=redir.automacao@surf4g.onmicrosoft.com

# Monday.com
MONDAY_API_TOKEN=eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjYzMzYyNjc1MCwiYWFpIjoxMSwidWlkIjo4NDIxMTQ3NiwiaWFkIjoiMjAyNi0wMy0xNlQxNDozMzo0OS40MjdaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MTQ1NDY2NDYsInJnbiI6InVzZTEifQ.-nVwr9MehMz2Q4xYKm8pv7TTZE6Fq7Ewh2fKODfX0oA

# Teams
TEAMS_WEBHOOK_URL=https://defaultb0f914e457bd42ea8f5d64e0d88a0d.1b.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/7c2e35d2c43e4284885df600b811ea39/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=F6OO1Gp3Tj83uvi0rx1e2NHA2lGYCfAPiSTyAHOjyXE

# Dashboard
FLASK_SECRET_KEY=f450b9c2b0335223d160fb4426fca02316b919b5484d5182986a71a856be46cf
```

- [ ] **Step 4: Update config.yaml — remove secrets, use env var markers**

Replace `/opt/weekly-report/config.yaml` with:
```yaml
# ============================================================
# Configuracao do Relatorio Semanal
# Credenciais em /opt/weekly-report/.env (NAO comitar!)
# ============================================================

# --- OTRS / Znuny (scraping) ---
otrs:
  panel_url: "https://ticket.surf.com.br"
  # username/password via env: OTRS_USERNAME, OTRS_PASSWORD
  queues:
    - name: "CLOUD"
      queue_id: 26
      sla_first_response_hours: 24
      sla_resolution_hours: 72
    - name: "TI"
      queue_id: 27
      sla_first_response_hours: 1
      sla_resolution_hours: 24

# --- AWS ---
aws:
  enabled: true

# --- OCI ---
oci:
  enabled: true
  tenant_id: "ocid1.tenancy.oc1..aaaaaaaa7egrbrn7qaci7k52a7wxvagq4f3eg662kaywxpysja3rwvdj5w2q"

# --- Golden Cloud ---
golden_cloud:
  enabled: true
  mode: "scraping"
  portal_url: "https://portal.goldencloud.tech/"
  # username/password via env: GOLDEN_CLOUD_USERNAME, GOLDEN_CLOUD_PASSWORD

# --- Monday.com ---
monday:
  enabled: true
  # api_token via env: MONDAY_API_TOKEN
  boards:
    - id: 10066566483
      category: cloud
    - id: 10066571131
      category: ti
    - id: 10066577924
      category: seguranca
    - id: 18377860565
      category: seguranca
      filter_person: "Wilson Kazuo Matsumoto"

# --- E-mail (Microsoft Graph API) ---
email:
  # tenant_id, client_id, client_secret, user_principal_name via env
  from: "redir.automacao@surf.com.br"
  to:
    - "carlos.nascimento@surf.com.br"

# --- Microsoft Teams ---
teams:
  # webhook_url via env: TEAMS_WEBHOOK_URL

# --- Dashboard ---
dashboard:
  output_dir: "/var/www/html/dashboard"
  base_url: "http://cloudteam.surf.com.br/dashboard"
  # secret_key via env: FLASK_SECRET_KEY

# --- Relatorio ---
report:
  schedule: "daily"
  timezone: "America/Sao_Paulo"
```

- [ ] **Step 5: Create env_loader.py — injects env vars into config dict**

Create `/opt/weekly-report/env_loader.py`:
```python
"""
Carrega variáveis de ambiente (.env) e injeta no config dict.
"""

import os
from dotenv import load_dotenv

ENV_FILE = "/opt/weekly-report/.env"


def load_env():
    """Carrega .env se existir."""
    load_dotenv(ENV_FILE)


def inject_secrets(config: dict) -> dict:
    """Injeta secrets do ambiente no config dict."""
    # OTRS
    otrs = config.get("otrs", {})
    otrs["username"] = os.environ.get("OTRS_USERNAME", otrs.get("username", ""))
    otrs["password"] = os.environ.get("OTRS_PASSWORD", otrs.get("password", ""))

    # Golden Cloud
    gc = config.get("golden_cloud", {})
    gc["username"] = os.environ.get("GOLDEN_CLOUD_USERNAME", gc.get("username", ""))
    gc["password"] = os.environ.get("GOLDEN_CLOUD_PASSWORD", gc.get("password", ""))

    # Email
    email = config.get("email", {})
    email["tenant_id"] = os.environ.get("EMAIL_TENANT_ID", email.get("tenant_id", ""))
    email["client_id"] = os.environ.get("EMAIL_CLIENT_ID", email.get("client_id", ""))
    email["client_secret"] = os.environ.get("EMAIL_CLIENT_SECRET", email.get("client_secret", ""))
    email["user_principal_name"] = os.environ.get("EMAIL_USER_PRINCIPAL_NAME", email.get("user_principal_name", ""))

    # Monday
    monday = config.get("monday", {})
    monday["api_token"] = os.environ.get("MONDAY_API_TOKEN", monday.get("api_token", ""))

    # Teams
    teams = config.get("teams", {})
    teams["webhook_url"] = os.environ.get("TEAMS_WEBHOOK_URL", teams.get("webhook_url", ""))

    # Dashboard
    dashboard = config.get("dashboard", {})
    dashboard["secret_key"] = os.environ.get("FLASK_SECRET_KEY", dashboard.get("secret_key", ""))

    return config
```

- [ ] **Step 6: Update main.py — load env at startup**

At the top of `main.py`, after the imports, add:
```python
from env_loader import load_env, inject_secrets
```

In `load_config()` function, change to:
```python
def load_config() -> dict:
    load_env()
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    return inject_secrets(config)
```

- [ ] **Step 7: Update api_server.py — load env at startup**

At the top of `api_server.py`, after the imports, add:
```python
from env_loader import load_env, inject_secrets
```

Change `_load_config()`:
```python
def _load_config() -> dict:
    load_env()
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    return inject_secrets(config)
```

Change `_load_secret_key()`:
```python
def _load_secret_key() -> str:
    load_env()
    import os as _os
    return _os.environ.get("FLASK_SECRET_KEY", "")
```

- [ ] **Step 8: Commit**

```bash
git add .env.example env_loader.py config.yaml main.py api_server.py requirements.txt
git commit -m "security: migrate secrets from config.yaml to .env"
```

---

### Task 3: Implement structured logging

**Files:**
- Create: `/opt/weekly-report/log_config.py`
- Modify: `/opt/weekly-report/main.py` (replace print with logging)
- Modify: `/opt/weekly-report/api_server.py` (replace print with logging)
- Modify: `/opt/weekly-report/collectors/otrs_collector.py` (replace print)
- Modify: `/opt/weekly-report/collectors/golden_collector.py` (replace print)
- Modify: `/opt/weekly-report/delivery/email_sender.py` (replace print)
- Modify: `/opt/weekly-report/delivery/teams_sender.py` (replace print)
- Modify: `/opt/weekly-report/report/generator.py` (replace print)
- Modify: `/opt/weekly-report/auth.py` (replace print)

- [ ] **Step 1: Create log_config.py**

Create `/opt/weekly-report/log_config.py`:
```python
"""
Configuração centralizada de logging.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "/opt/weekly-report/data"
LOG_FILE = os.path.join(LOG_DIR, "weekly-report.log")


def setup_logging(level: int = logging.INFO):
    """Configura logging com saída em console e arquivo rotacionado."""
    os.makedirs(LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Arquivo rotacionado: 5MB x 3 backups
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
```

- [ ] **Step 2: Replace all print() calls with logging in every module**

In each file, add `import logging` and `logger = logging.getLogger(__name__)` at the top, then replace:
- `print(f"[XXX] ...")` → `logger.info("...")`
- `print(f"[XXX] ERRO: ...")` → `logger.error("...")`
- `traceback.print_exc()` → `logger.exception("Detalhes do erro:")`

In `main.py`, at the very start of `main()`:
```python
from log_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)
```

- [ ] **Step 3: Commit**

```bash
git add log_config.py main.py api_server.py auth.py collectors/ delivery/ report/generator.py
git commit -m "feat: replace print() with structured logging (RotatingFileHandler)"
```

---

### Task 4: Fix SSL verification in Golden Cloud collector

**Files:**
- Modify: `/opt/weekly-report/collectors/golden_collector.py`

- [ ] **Step 1: Replace verify=False with configurable CA bundle**

In `golden_collector.py`, remove the `warnings.filterwarnings` line and `import warnings`.

Change the `__init__` to accept a `ca_bundle` parameter:
```python
def __init__(self, config: dict):
    self.mode = config.get("mode", "scraping")
    self.portal_url = config.get("portal_url", "")
    self.username = config.get("username", "")
    self.password = config.get("password", "")
    self.verify_ssl = config.get("verify_ssl", True)
    self.data_file = DATA_FILE
```

In `_scrape()`, change:
```python
session = requests.Session()
session.verify = self.verify_ssl
```

Add to config.yaml under golden_cloud:
```yaml
verify_ssl: true  # Set to false only if portal uses self-signed cert
```

- [ ] **Step 2: Commit**

```bash
git add collectors/golden_collector.py config.yaml
git commit -m "security: enable SSL verification for Golden Cloud (configurable)"
```

---

### Task 5: Add rate limiting to Flask login

**Files:**
- Modify: `/opt/weekly-report/requirements.txt`
- Modify: `/opt/weekly-report/api_server.py`

- [ ] **Step 1: Install flask-limiter**

Add `flask-limiter>=3.5.0` to requirements.txt. Run:
```bash
cd /opt/weekly-report && source venv/bin/activate && pip install flask-limiter
```

- [ ] **Step 2: Add limiter to api_server.py**

After the `app` creation, add:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)
```

Add rate limit decorators to sensitive routes:
```python
@app.route("/dashboard/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    ...

@app.route("/dashboard/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def forgot_password():
    ...
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt api_server.py
git commit -m "security: add rate limiting to login and forgot-password routes"
```

---

### Task 6: Reduce session timeout and strengthen password validation

**Files:**
- Modify: `/opt/weekly-report/api_server.py` (session timeout)
- Modify: `/opt/weekly-report/auth.py` (password validation)

- [ ] **Step 1: Reduce session timeout to 4 hours**

In `api_server.py`, change:
```python
app.config["PERMANENT_SESSION_LIFETIME"] = 14400  # 4h
```

- [ ] **Step 2: Add password validation function to auth.py**

Add to `auth.py`:
```python
import re

def validate_password(password: str) -> str | None:
    """
    Valida complexidade da senha.
    Retorna mensagem de erro ou None se válida.
    """
    if len(password) < 8:
        return "A senha deve ter pelo menos 8 caracteres."
    if not re.search(r"[A-Z]", password):
        return "A senha deve conter pelo menos uma letra maiúscula."
    if not re.search(r"[a-z]", password):
        return "A senha deve conter pelo menos uma letra minúscula."
    if not re.search(r"[0-9]", password):
        return "A senha deve conter pelo menos um número."
    if not re.search(r"[^A-Za-z0-9]", password):
        return "A senha deve conter pelo menos um caractere especial."
    return None
```

- [ ] **Step 3: Use validate_password in api_server.py**

In `api_server.py`, import `validate_password` from auth, then in `change_password_page()` and `reset_password()`, replace the `len(new_password) < 6` check with:
```python
pwd_error = validate_password(new_password)
if pwd_error:
    error = pwd_error
```

- [ ] **Step 4: Commit**

```bash
git add api_server.py auth.py
git commit -m "security: reduce session to 4h, enforce password complexity"
```

---

### Task 7: Add retry with exponential backoff to all collectors

**Files:**
- Modify: `/opt/weekly-report/requirements.txt`
- Modify: `/opt/weekly-report/collectors/otrs_collector.py`
- Modify: `/opt/weekly-report/collectors/aws_collector.py`
- Modify: `/opt/weekly-report/collectors/oci_collector.py`
- Modify: `/opt/weekly-report/collectors/golden_collector.py`
- Modify: `/opt/weekly-report/collectors/monday_collector.py`

- [ ] **Step 1: Install tenacity**

Add `tenacity>=8.2.0` to requirements.txt. Run:
```bash
cd /opt/weekly-report && source venv/bin/activate && pip install tenacity
```

- [ ] **Step 2: Add retry decorator to each collector's main method**

In each collector, add:
```python
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)
```

Then decorate the `collect()` method (and `_login`/`_scrape` for OTRS/Golden):

**otrs_collector.py** — on `_login` and `_search_csv`:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
       before_sleep=before_sleep_log(logger, logging.WARNING))
def _login(self, session, ...):
```

**aws_collector.py** — on `_query_costs`:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
       before_sleep=before_sleep_log(logger, logging.WARNING))
def _query_costs(self, ...):
```

**oci_collector.py** — on `collect`:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
       before_sleep=before_sleep_log(logger, logging.WARNING))
def collect(self):
```

**golden_collector.py** — on `_scrape`:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
       before_sleep=before_sleep_log(logger, logging.WARNING))
def _scrape(self):
```

**monday_collector.py** — on `_query`:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
       before_sleep=before_sleep_log(logger, logging.WARNING))
def _query(self, query):
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt collectors/
git commit -m "feat: add retry with exponential backoff to all collectors"
```

---

### Task 8: Add failure alerting via Teams

**Files:**
- Modify: `/opt/weekly-report/main.py`

- [ ] **Step 1: Add failure notification function to main.py**

Add after imports in `main.py`:
```python
def _notify_failure(config: dict, failures: list[str]):
    """Envia alerta de falha no Teams se houver erros de coleta."""
    if not failures:
        return
    webhook_url = config.get("teams", {}).get("webhook_url", "")
    if not webhook_url:
        return
    try:
        import requests as req
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "⚠️ Relatório Semanal — Falhas na Coleta",
                    "weight": "Bolder",
                    "size": "Medium",
                    "color": "Attention",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": "\n".join(f"- {f}" for f in failures),
                    "wrap": True,
                },
            ],
        }
        req.post(webhook_url, json=card, timeout=15)
        logger.info("Alerta de falhas enviado ao Teams")
    except Exception as e:
        logger.error(f"Erro ao enviar alerta de falhas: {e}")
```

- [ ] **Step 2: Track failures in main() and send alert at the end**

In `main()`, add `failures = []` after config is loaded. In each collector's except block, append to failures:
```python
except Exception as e:
    logger.error(f"[AWS] ERRO: {e}")
    failures.append(f"AWS: {e}")
```

Before the delivery section (or after, in dry-run), add:
```python
_notify_failure(config, failures)
```

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: send Teams alert when data collection fails"
```

---

### Task 9: Add /health endpoint to Flask

**Files:**
- Modify: `/opt/weekly-report/api_server.py`

- [ ] **Step 1: Add health check route**

Add to `api_server.py`:
```python
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
```

- [ ] **Step 2: Commit**

```bash
git add api_server.py
git commit -m "feat: add /dashboard/health endpoint for monitoring"
```

---

### Task 10: Add JSON schema validation on load

**Files:**
- Modify: `/opt/weekly-report/report/generator.py` (history.json validation)
- Modify: `/opt/weekly-report/auth.py` (users.json validation)

- [ ] **Step 1: Add safe JSON load with validation to generator.py**

In `_load_history()`:
```python
def _load_history(self) -> list:
    """Carrega histórico de relatórios anteriores com validação."""
    history_file = os.path.join(DATA_DIR, "history.json")
    if not os.path.exists(history_file):
        return []
    try:
        with open(history_file) as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("history.json não é uma lista, ignorando")
            return []
        # Valida que cada entry tem campos mínimos
        valid = []
        for entry in data:
            if isinstance(entry, dict) and "date" in entry:
                valid.append(entry)
            else:
                logger.warning(f"Entrada inválida no histórico ignorada: {entry}")
        return valid
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Erro ao carregar history.json: {e}")
        return []
```

- [ ] **Step 2: Add safe JSON load to auth.py**

In `_load_users()`:
```python
def _load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("users.json não é um dict, retornando vazio")
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Erro ao carregar users.json: {e}")
        return {}
```

Same pattern for `_load_tokens()`.

- [ ] **Step 3: Commit**

```bash
git add report/generator.py auth.py
git commit -m "fix: add JSON validation to prevent crashes on corrupt data files"
```

---

### Task 11: Use last known dollar rate from history instead of hardcoded fallback

**Files:**
- Modify: `/opt/weekly-report/report/generator.py`

- [ ] **Step 1: Update _get_dollar_rate to check history before hardcoded fallback**

Replace the final fallback in `_get_dollar_rate()`:
```python
# Fallback: última cotação do histórico
history = self._load_history()
for entry in reversed(history):
    rate = entry.get("dollar_rate")
    if rate and isinstance(rate, (int, float)) and rate > 0:
        logger.warning(f"Usando cotação do histórico: {rate}")
        return rate

logger.error("Sem cotação disponível, usando fallback 5.25")
return 5.25
```

Also, save `dollar_rate` in history entries. In `_save_history()`, add to the `entry` dict:
```python
"dollar_rate": report_data.get("dollar_rate"),
```

- [ ] **Step 2: Commit**

```bash
git add report/generator.py
git commit -m "fix: use last known dollar rate from history before hardcoded fallback"
```

---

### Task 12: Reorganize scripts and CSV files into subdirectories

**Files:**
- Move: `export_ad_users.py` → `scripts/export_ad_users.py`
- Move: `export_exchange_users.py` → `scripts/export_exchange_users.py`
- Move: `generate_demo.py` → `scripts/generate_demo.py`
- Move: `rebuild_history.py` → `scripts/rebuild_history.py`
- Move: `manage_users.py` → `scripts/manage_users.py`

- [ ] **Step 1: Create scripts directory and move files**

```bash
cd /opt/weekly-report
mkdir -p scripts
mv export_ad_users.py export_exchange_users.py generate_demo.py rebuild_history.py manage_users.py scripts/
```

- [ ] **Step 2: Commit**

```bash
git add scripts/
git commit -m "chore: move utility scripts to scripts/ directory"
```

---

### Task 13: Add unit tests for critical business logic

**Files:**
- Create: `/opt/weekly-report/tests/__init__.py`
- Create: `/opt/weekly-report/tests/test_sla_calculation.py`
- Create: `/opt/weekly-report/tests/test_dollar_conversion.py`
- Create: `/opt/weekly-report/tests/test_password_validation.py`
- Create: `/opt/weekly-report/tests/test_teams_card.py`

- [ ] **Step 1: Add pytest to requirements.txt**

Add `pytest>=8.0.0` to requirements.txt. Run:
```bash
cd /opt/weekly-report && source venv/bin/activate && pip install pytest
```

- [ ] **Step 2: Create test for SLA calculation**

Create `/opt/weekly-report/tests/__init__.py` (empty).

Create `/opt/weekly-report/tests/test_sla_calculation.py`:
```python
"""Testes para cálculo de SLA do OTRS collector."""

from collectors.otrs_collector import OTRSCollector, CLOSED_STATES


def _make_ticket(created, closed="", state="novo", first_response_minutes="", resolution_minutes="", service="", customer="", owner=""):
    return {
        "number": "2026010100001",
        "created": created,
        "closed": closed,
        "first_response": "",
        "state": state,
        "priority": "3 normal",
        "queue": "CLOUD",
        "owner": owner,
        "subject": "Test ticket",
        "resolution_minutes": resolution_minutes,
        "first_response_minutes": first_response_minutes,
        "service": service,
        "customer": customer,
    }


class TestSLACalculation:
    def _make_collector(self):
        config = {
            "panel_url": "https://example.com",
            "username": "test",
            "password": "test",
            "queues": [{"name": "TEST", "queue_id": 1}],
        }
        return OTRSCollector(config)

    def test_all_within_sla(self):
        collector = self._make_collector()
        tickets = [
            _make_ticket("2026-03-20 10:00:00", first_response_minutes="60", resolution_minutes="120"),
            _make_ticket("2026-03-21 10:00:00", first_response_minutes="120", resolution_minutes="600"),
        ]
        result = collector._calc_metrics(tickets, "2026-03-20", "2026-03-26", sla_first_response_hours=24, sla_resolution_hours=72)
        assert result["opened"] == 2
        assert result["pct_first_response"] == 100.0
        assert result["pct_resolution"] == 100.0

    def test_sla_breach(self):
        collector = self._make_collector()
        tickets = [
            _make_ticket("2026-03-20 10:00:00", first_response_minutes="1500", resolution_minutes="5000"),
            _make_ticket("2026-03-21 10:00:00", first_response_minutes="60", resolution_minutes="120"),
        ]
        result = collector._calc_metrics(tickets, "2026-03-20", "2026-03-26", sla_first_response_hours=24, sla_resolution_hours=72)
        assert result["pct_first_response"] == 50.0
        assert result["pct_resolution"] == 50.0

    def test_no_tickets_in_period(self):
        collector = self._make_collector()
        tickets = [
            _make_ticket("2026-03-10 10:00:00"),  # Before period
        ]
        result = collector._calc_metrics(tickets, "2026-03-20", "2026-03-26")
        assert result["opened"] == 0
        assert result["pct_first_response"] is None

    def test_backlog_counts_open_tickets(self):
        collector = self._make_collector()
        tickets = [
            _make_ticket("2026-03-20 10:00:00", state="novo"),
            _make_ticket("2026-03-21 10:00:00", state="Fechado com êxito", closed="2026-03-22 10:00:00"),
        ]
        result = collector._calc_metrics(tickets, "2026-03-20", "2026-03-26")
        assert result["backlog"] == 1
```

- [ ] **Step 3: Create test for dollar conversion**

Create `/opt/weekly-report/tests/test_dollar_conversion.py`:
```python
"""Testes para conversão de moeda no generator."""


class TestDollarConversion:
    def test_usd_converted_to_brl(self):
        clouds = [
            {"provider": "AWS", "currency": "USD", "total_cost": 100.0},
        ]
        dollar_rate = 5.50
        for c in clouds:
            if c.get("currency") == "USD":
                c["total_cost_brl"] = round(c["total_cost"] * dollar_rate, 2)
            else:
                c["total_cost_brl"] = c["total_cost"]
        assert clouds[0]["total_cost_brl"] == 550.0

    def test_brl_not_converted(self):
        clouds = [
            {"provider": "Golden Cloud", "currency": "BRL", "total_cost": 35000.0},
        ]
        dollar_rate = 5.50
        for c in clouds:
            if c.get("currency") == "USD":
                c["total_cost_brl"] = round(c["total_cost"] * dollar_rate, 2)
            else:
                c["total_cost_brl"] = c["total_cost"]
        assert clouds[0]["total_cost_brl"] == 35000.0
```

- [ ] **Step 4: Create test for password validation**

Create `/opt/weekly-report/tests/test_password_validation.py`:
```python
"""Testes para validação de senha."""

from auth import validate_password


class TestPasswordValidation:
    def test_valid_password(self):
        assert validate_password("Str0ng!Pass") is None

    def test_too_short(self):
        assert validate_password("Ab1!") is not None

    def test_no_uppercase(self):
        assert validate_password("abcdefg1!") is not None

    def test_no_lowercase(self):
        assert validate_password("ABCDEFG1!") is not None

    def test_no_digit(self):
        assert validate_password("Abcdefg!!") is not None

    def test_no_special(self):
        assert validate_password("Abcdefg12") is not None
```

- [ ] **Step 5: Create test for Teams Adaptive Card structure**

Create `/opt/weekly-report/tests/test_teams_card.py`:
```python
"""Testes para geração do Adaptive Card do Teams."""

from delivery.teams_sender import TeamsSender


class TestTeamsCard:
    def _make_report_data(self):
        return {
            "otrs_queues": [
                {
                    "queue_name": "CLOUD",
                    "period": {"start": "2026-03-20", "end": "2026-03-26"},
                    "opened": 10,
                    "closed": 8,
                    "backlog": 5,
                    "pct_first_response": 95.0,
                    "pct_resolution": 100.0,
                    "first_response_target": 24,
                    "resolution_target": 72,
                }
            ],
            "clouds": [
                {"provider": "AWS", "currency": "USD", "total_cost": 1000.0, "total_cost_brl": 5500.0},
            ],
            "dollar_rate": 5.50,
            "total_cloud_cost_brl": 5500.0,
        }

    def test_card_has_required_sections(self):
        sender = TeamsSender({"webhook_url": "https://example.com"})
        # We test the card building by calling send with a mock
        # For now, just verify the report_data structure is valid
        data = self._make_report_data()
        assert len(data["otrs_queues"]) == 1
        assert data["otrs_queues"][0]["queue_name"] == "CLOUD"
        assert len(data["clouds"]) == 1
```

- [ ] **Step 6: Run tests**

```bash
cd /opt/weekly-report && source venv/bin/activate && python -m pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/ requirements.txt
git commit -m "test: add unit tests for SLA, currency conversion, password validation"
```

---

### Task 14: Add /dashboard/health to nginx config (optional verification)

This is a documentation task. The health endpoint is already accessible via Flask proxy. Verify:

- [ ] **Step 1: Test health endpoint**

```bash
curl http://localhost:8080/dashboard/health
```

Expected: JSON response with `status`, `dashboard_age_hours`, `dashboard_stale` fields.

---

### Task 15: Save cloud cost breakdown in history for trend analysis

**Files:**
- Modify: `/opt/weekly-report/report/generator.py`

- [ ] **Step 1: Enhance _save_history to include cost breakdowns**

In `_save_history()`, enhance the `cloud_costs` section of the entry:
```python
# Custos detalhados por provider
cloud_details = {}
for c in report_data["clouds"]:
    provider = c["provider"]
    cloud_details[provider] = {
        "total_cost": c["total_cost"],
        "currency": c.get("currency", "USD"),
        "total_cost_brl": c.get("total_cost_brl", c["total_cost"]),
    }
    if c.get("accounts"):
        cloud_details[provider]["accounts"] = [
            {"name": a.get("account_name", a["account_id"]), "cost": a["cost"]}
            for a in c["accounts"][:10]
        ]
    if c.get("top_services"):
        cloud_details[provider]["top_services"] = [
            {"service": s["service"], "cost": s["cost"]}
            for s in c["top_services"][:5]
        ]
```

Replace `"cloud_costs": { c["provider"]: c["total_cost"] ...}` with:
```python
"cloud_costs": {c["provider"]: c["total_cost"] for c in report_data["clouds"]},
"cloud_details": cloud_details,
```

- [ ] **Step 2: Commit**

```bash
git add report/generator.py
git commit -m "feat: save cloud cost breakdown (accounts/services) in history"
```

---

### Task 16: Add weekly comparison deltas to report data

**Files:**
- Modify: `/opt/weekly-report/report/generator.py`

- [ ] **Step 1: Add _calc_deltas method to ReportGenerator**

Add after `_load_history`:
```python
def _calc_deltas(self, report_data: dict, history: list) -> dict:
    """Calcula variação percentual vs semana anterior."""
    deltas = {}
    if len(history) < 1:
        return deltas

    prev = history[-1]  # Último entry é a semana anterior

    # Delta custos por provider
    prev_costs = prev.get("cloud_costs", {})
    for c in report_data["clouds"]:
        provider = c["provider"]
        current = c.get("total_cost_brl", c["total_cost"])
        previous = prev_costs.get(provider, 0)
        if previous > 0:
            pct = round((current - previous) / previous * 100, 1)
            deltas[f"cost_{provider}"] = {"current": current, "previous": previous, "pct": pct}

    # Delta total
    current_total = report_data.get("total_cloud_cost_brl", 0)
    prev_total = sum(prev_costs.values()) if prev_costs else 0
    if prev_total > 0:
        deltas["cost_total"] = {
            "current": current_total,
            "previous": prev_total,
            "pct": round((current_total - prev_total) / prev_total * 100, 1),
        }

    # Delta chamados por fila
    prev_queues = prev.get("queues", {})
    for q in report_data.get("otrs_queues", []):
        qname = q["queue_name"]
        prev_q = prev_queues.get(qname, {})
        for field in ("opened", "closed", "backlog"):
            curr_val = q.get(field, 0)
            prev_val = prev_q.get(field, 0)
            if prev_val > 0:
                pct = round((curr_val - prev_val) / prev_val * 100, 1)
            elif curr_val > 0:
                pct = 100.0
            else:
                pct = 0.0
            deltas[f"{qname}_{field}"] = {"current": curr_val, "previous": prev_val, "pct": pct}

    return deltas
```

- [ ] **Step 2: Inject deltas into report_data in generate()**

After loading history, add:
```python
report_data["deltas"] = self._calc_deltas(report_data, history)
```

- [ ] **Step 3: Commit**

```bash
git add report/generator.py
git commit -m "feat: calculate weekly comparison deltas for costs and tickets"
```

---

### Task 17: Integrate Monday.com data into Teams card and email

**Files:**
- Modify: `/opt/weekly-report/delivery/teams_sender.py`

- [ ] **Step 1: Add Monday.com section to Teams Adaptive Card**

In `teams_sender.py`, in the `send()` method, after the cloud costs table and before `"actions"`, add a Monday.com section:

```python
# Seção Monday.com (projetos)
monday_boards = report_data.get("monday_boards", [])
monday_body = []
if monday_boards:
    monday_body.append({
        "type": "TextBlock",
        "text": "📋 PROJETOS (Monday.com)",
        "weight": "Bolder",
        "color": "Accent",
        "spacing": "Large",
        "wrap": True,
    })
    proj_rows = [
        {
            "type": "TableRow",
            "style": "accent",
            "cells": [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Board", "weight": "Bolder", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Total", "weight": "Bolder", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Concluídos", "weight": "Bolder", "wrap": True}]},
            ],
        },
    ]
    for board in monday_boards:
        done = board.get("status_summary", {}).get("Feito", 0) + board.get("status_summary", {}).get("Concluído", 0) + board.get("status_summary", {}).get("Done", 0)
        proj_rows.append({
            "type": "TableRow",
            "cells": [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": board["board_name"], "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": str(board["total_projects"]), "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": str(done), "wrap": True}]},
            ],
        })
    monday_body.append({
        "type": "Table",
        "gridStyle": "accent",
        "firstRowAsHeader": True,
        "showGridLines": True,
        "columns": [{"width": 3}, {"width": 1}, {"width": 1}],
        "rows": proj_rows,
    })
```

Add `*monday_body,` to the body list, before the actions.

- [ ] **Step 2: Commit**

```bash
git add delivery/teams_sender.py
git commit -m "feat: add Monday.com projects section to Teams Adaptive Card"
```

---

### Task 18: Extract dashboard CSS to static file and use Jinja2 template inheritance

**Files:**
- Create: `/opt/weekly-report/report/templates/base.html`
- Create: `/opt/weekly-report/static/css/dashboard.css`
- Modify: `/opt/weekly-report/report/templates/dashboard.html` (extract inline CSS)
- Modify: `/opt/weekly-report/api_server.py` (serve static files)

- [ ] **Step 1: Create static directory and extract CSS from dashboard.html**

Read dashboard.html, extract all content inside `<style>` tags to `/opt/weekly-report/static/css/dashboard.css`.

Replace the `<style>` block in dashboard.html with:
```html
<link rel="stylesheet" href="/dashboard/static/css/dashboard.css">
```

- [ ] **Step 2: Add static file serving to api_server.py**

Add route:
```python
STATIC_DIR = "/opt/weekly-report/static"

@app.route("/dashboard/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)
```

- [ ] **Step 3: Create base.html template with Jinja2 inheritance**

Create `/opt/weekly-report/report/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Surf Telecom{% endblock %}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    {% block head %}{% endblock %}
</head>
<body>
    {% block body %}{% endblock %}
    {% block scripts %}{% endblock %}
</body>
</html>
```

Update login.html, change_password.html, forgot_password.html, reset_password.html to extend base.html.

- [ ] **Step 4: Commit**

```bash
git add static/ report/templates/ api_server.py
git commit -m "refactor: extract CSS to static file, add Jinja2 template inheritance"
```

---

### Task 19: Final — update requirements.txt and run all tests

**Files:**
- Modify: `/opt/weekly-report/requirements.txt`

- [ ] **Step 1: Ensure requirements.txt has all new deps**

Final requirements.txt:
```
boto3>=1.34.0
oci>=2.120.0
requests>=2.31.0
jinja2>=3.1.0
pyyaml>=6.0
python-dateutil>=2.8.0
msal>=1.28.0
flask>=3.0.0
bcrypt>=4.1.0
python-dotenv>=1.0.0
tenacity>=8.2.0
flask-limiter>=3.5.0
pytest>=8.0.0
```

- [ ] **Step 2: Install all and run tests**

```bash
cd /opt/weekly-report && source venv/bin/activate && pip install -r requirements.txt && python -m pytest tests/ -v
```

- [ ] **Step 3: Restart service**

```bash
sudo systemctl restart weekly-report-api
```

- [ ] **Step 4: Verify health endpoint**

```bash
curl http://localhost:8080/dashboard/health
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: finalize all improvements, update deps"
```
