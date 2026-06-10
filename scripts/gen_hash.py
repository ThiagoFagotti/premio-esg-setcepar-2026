"""Gera um hash de senha (werkzeug / PBKDF2) para colar na tabela `usuarios`.

Uso:
    python scripts/gen_hash.py "senha-aqui"

Útil para definir/trocar senhas reais de jurados sem mexer no código:
gere o hash aqui e faça um UPDATE/INSERT na tabela `usuarios` no BigQuery.
"""
import sys

from werkzeug.security import generate_password_hash


def main() -> None:
    if len(sys.argv) != 2:
        print('Uso: python scripts/gen_hash.py "senha"')
        sys.exit(1)
    print(generate_password_hash(sys.argv[1]))


if __name__ == "__main__":
    main()
