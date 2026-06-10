"""Autenticação dos jurados a partir da tabela `usuarios` do BigQuery.

- A lista de usuários é lida uma vez (cache em memória) e a senha é comparada
  diretamente (texto puro — decisão institucional p/ app interno pequeno).
- Não existe mais o conceito de "admin": todo login é tratado como jurado.
"""
import logging
from functools import wraps

from flask import redirect, session, url_for

from . import bq

logger = logging.getLogger(__name__)

_usuarios: dict[str, dict] | None = None


def get_usuarios() -> dict[str, dict]:
    """Carrega os usuários uma única vez (cache). Lazy para não quebrar no import."""
    global _usuarios
    if _usuarios is None:
        _usuarios = bq.carregar_usuarios()
    return _usuarios


def autenticar(username: str, password: str) -> dict | None:
    """Retorna o registro do usuário se as credenciais forem válidas, senão None."""
    usuario = get_usuarios().get(username)
    if usuario and usuario["senha"] == password:
        return usuario
    return None


def login_required(view):
    """Redireciona para o login se não houver sessão (elimina os ifs repetidos)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped
