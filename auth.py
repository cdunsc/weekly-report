"""
Gerenciamento de usuários e autenticação.
Armazena credenciais em JSON com senhas hash (bcrypt).
"""

import json
import os
import secrets
from datetime import datetime, timedelta

import bcrypt

USERS_FILE = "/opt/weekly-report/data/users.json"
RESET_TOKENS_FILE = "/opt/weekly-report/data/reset_tokens.json"


def _load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}


def _save_users(users: dict):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def _load_tokens() -> dict:
    if os.path.exists(RESET_TOKENS_FILE):
        with open(RESET_TOKENS_FILE) as f:
            return json.load(f)
    return {}


def _save_tokens(tokens: dict):
    os.makedirs(os.path.dirname(RESET_TOKENS_FILE), exist_ok=True)
    with open(RESET_TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


def add_user(username: str, password: str, email: str = "",
             must_change_password: bool = True):
    """Adiciona ou atualiza um usuário."""
    users = _load_users()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    existing = users.get(username, {})
    users[username] = {
        "password_hash": hashed,
        "email": email or existing.get("email", ""),
        "must_change_password": must_change_password,
    }
    _save_users(users)


def remove_user(username: str) -> bool:
    """Remove um usuário. Retorna True se existia."""
    users = _load_users()
    if username in users:
        del users[username]
        _save_users(users)
        return True
    return False


def verify_user(username: str, password: str) -> bool:
    """Verifica credenciais."""
    users = _load_users()
    user = users.get(username)
    if not user:
        return False
    return bcrypt.checkpw(password.encode(), user["password_hash"].encode())


def get_user(username: str) -> dict | None:
    """Retorna dados do usuário (sem a senha)."""
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    return {
        "username": username,
        "email": user.get("email", ""),
        "must_change_password": user.get("must_change_password", False),
    }


def change_password(username: str, new_password: str):
    """Altera a senha e remove flag de troca obrigatória."""
    users = _load_users()
    if username not in users:
        return False
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    users[username]["password_hash"] = hashed
    users[username]["must_change_password"] = False
    _save_users(users)
    return True


def get_user_by_email(email: str) -> dict | None:
    """Encontra usuário pelo e-mail."""
    users = _load_users()
    for username, data in users.items():
        if data.get("email", "").lower() == email.lower():
            return {"username": username, **data}
    return None


def create_reset_token(username: str) -> str:
    """Gera token de reset com validade de 1 hora."""
    tokens = _load_tokens()
    token = secrets.token_urlsafe(32)
    tokens[token] = {
        "username": username,
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
    }
    # Limpa tokens expirados
    now = datetime.now()
    tokens = {
        t: d for t, d in tokens.items()
        if datetime.fromisoformat(d["expires_at"]) > now
    }
    _save_tokens(tokens)
    return token


def verify_reset_token(token: str) -> str | None:
    """Valida token e retorna username. None se inválido/expirado."""
    tokens = _load_tokens()
    data = tokens.get(token)
    if not data:
        return None
    if datetime.fromisoformat(data["expires_at"]) < datetime.now():
        del tokens[token]
        _save_tokens(tokens)
        return None
    return data["username"]


def consume_reset_token(token: str):
    """Remove token após uso."""
    tokens = _load_tokens()
    tokens.pop(token, None)
    _save_tokens(tokens)


def list_users() -> list[dict]:
    """Retorna lista de usuários com info."""
    users = _load_users()
    return [
        {
            "username": u,
            "email": d.get("email", ""),
            "must_change_password": d.get("must_change_password", False),
        }
        for u, d in users.items()
    ]
