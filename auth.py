"""Re-export do modulo centralizado de autenticacao."""
import importlib.util as _ilu
import sys as _sys

_spec = _ilu.spec_from_file_location("shared_auth", "/opt/shared-auth/auth.py")
_mod = _ilu.module_from_spec(_spec)
_sys.modules["shared_auth"] = _mod
_spec.loader.exec_module(_mod)

# Re-export all public names
from shared_auth import (  # noqa: E402,F401
    add_user,
    remove_user,
    verify_user,
    get_user,
    change_password,
    get_user_by_email,
    create_reset_token,
    verify_reset_token,
    consume_reset_token,
    validate_password,
    list_users,
)
