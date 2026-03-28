#!/usr/bin/env python3
"""
Gerenciar usuários do dashboard.

Uso:
    python manage_users.py add <usuario> <senha> <email>
    python manage_users.py add <usuario> <senha> <email> --no-change
    python manage_users.py remove <usuario>
    python manage_users.py list
"""

import sys

from auth import add_user, remove_user, list_users


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add":
        if len(sys.argv) < 5:
            print("Uso: python manage_users.py add <usuario> <senha> <email> [--no-change]")
            sys.exit(1)
        username, password, email = sys.argv[2], sys.argv[3], sys.argv[4]
        must_change = "--no-change" not in sys.argv
        add_user(username, password, email, must_change_password=must_change)
        flag = " (troca de senha obrigatória no primeiro login)" if must_change else ""
        print(f"Usuário '{username}' criado/atualizado.{flag}")

    elif cmd == "remove":
        if len(sys.argv) != 3:
            print("Uso: python manage_users.py remove <usuario>")
            sys.exit(1)
        username = sys.argv[2]
        if remove_user(username):
            print(f"Usuário '{username}' removido.")
        else:
            print(f"Usuário '{username}' não encontrado.")

    elif cmd == "list":
        users = list_users()
        if users:
            print("Usuários cadastrados:")
            for u in users:
                change = " [troca pendente]" if u["must_change_password"] else ""
                print(f"  - {u['username']} ({u['email'] or 'sem email'}){change}")
        else:
            print("Nenhum usuário cadastrado.")

    else:
        print(f"Comando desconhecido: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
