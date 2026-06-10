"""Configuração centralizada lida do ambiente (.env).

Falha de forma clara no startup se algo obrigatório estiver ausente — sem
fallbacks inseguros. As variáveis mortas do .env antigo foram removidas; tudo
que é referenciado aqui é o que o app realmente usa.
"""
import os

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Erro de configuração detectado no startup."""


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"Variável de ambiente obrigatória ausente: {name}. "
            "Defina-a no .env ou no ambiente do Cloud Run."
        )
    return value


# Flask — OBRIGATÓRIA, sem o antigo fallback 'default_secret_key_for_dev'.
SECRET_KEY = _required("FLASK_SECRET_KEY")

# BigQuery — projeto, dataset e nomes de tabela (não mais hardcoded).
BQ_PROJECT = os.environ.get("BIGQUERY_PROJECT_ID", "iptc-banco-de-dados")
BQ_DATASET = os.environ.get("BIGQUERY_DATASET", "premio_esg_setcepar_2026")
TABLE_USUARIOS = os.environ.get("BIGQUERY_TABLE_USUARIOS", "usuarios")
TABLE_PROJETOS = os.environ.get("BIGQUERY_TABLE_PROJETOS", "projetos")
TABLE_AVALIACOES = os.environ.get("BIGQUERY_TABLE_AVALIACOES", "avaliacoes")


def table_ref(table: str) -> str:
    """Referência totalmente qualificada `projeto.dataset.tabela`."""
    return f"{BQ_PROJECT}.{BQ_DATASET}.{table}"


# Domínio do prêmio (decisões fechadas no ROADMAP §2/§5).
CATEGORIAS = [
    "Responsabilidade Ambiental",
    "Responsabilidade Social",
    "Governança Corporativa",
]
PORTES = ["Micro/Pequenas", "Médias/Grandes"]

# Fuso usado para o carimbo de data/hora das avaliações.
TIMEZONE = "America/Sao_Paulo"
