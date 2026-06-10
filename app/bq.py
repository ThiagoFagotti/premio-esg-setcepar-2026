"""Camada de acesso ao BigQuery.

- O cliente é inicializado de forma preguiçosa (não quebra no import; antes
  `client = get_bigquery_client()` rodava em tempo de import).
- Gravação é APPEND-ONLY via INSERT (DML). Não há UPDATE nem campo `situacao`.
- "Já avaliado" é computado por LEFT JOIN / contagem, não por estado na linha.
"""
import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from google.cloud import bigquery

from . import config

logger = logging.getLogger(__name__)

_client: bigquery.Client | None = None


def get_client() -> bigquery.Client:
    """Cliente BigQuery (singleton preguiçoso). O SDK resolve as credenciais."""
    global _client
    if _client is None:
        _client = bigquery.Client(project=config.BQ_PROJECT)
        logger.info("Cliente BigQuery inicializado (projeto=%s)", config.BQ_PROJECT)
    return _client


def _agora_sp() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def _params(job_config_params: list) -> bigquery.QueryJobConfig:
    return bigquery.QueryJobConfig(query_parameters=job_config_params)


# --- Leitura --------------------------------------------------------------

def carregar_usuarios() -> dict[str, dict]:
    """Lê os usuários ativos. Retorna username -> {senha_hash, nome_jurado}."""
    query = f"""
        SELECT username, senha_hash, nome_jurado
        FROM `{config.table_ref(config.TABLE_USUARIOS)}`
        WHERE ativo = TRUE
    """
    usuarios = {
        row.username: {"senha_hash": row.senha_hash, "nome_jurado": row.nome_jurado}
        for row in get_client().query(query).result()
    }
    logger.info("Carregados %d usuários ativos do BigQuery", len(usuarios))
    return usuarios


def carregar_projetos_pendentes(jurado: str) -> list[dict]:
    """Todos os projetos ainda NÃO avaliados pelo jurado (todas as categorias/portes).

    Numa única ida ao BigQuery; alimenta a cascata Categoria -> Porte -> Empresa
    montada no navegador (sem recarregar a página a cada seleção).
    """
    query = f"""
        SELECT p.id_projeto, p.empresa, p.porte, p.categoria, p.projeto
        FROM `{config.table_ref(config.TABLE_PROJETOS)}` p
        LEFT JOIN `{config.table_ref(config.TABLE_AVALIACOES)}` a
          ON a.id_projeto = p.id_projeto AND a.avaliador = @jurado
        WHERE a.id_projeto IS NULL
        ORDER BY p.categoria, p.porte, p.empresa
    """
    job_config = _params([
        bigquery.ScalarQueryParameter("jurado", "STRING", jurado),
    ])
    return [
        {"id_projeto": r.id_projeto, "empresa": r.empresa, "porte": r.porte,
         "categoria": r.categoria, "projeto": r.projeto}
        for r in get_client().query(query, job_config=job_config).result()
    ]


def obter_projeto(id_projeto: str) -> dict | None:
    """Dados de um projeto do catálogo (substitui obter_projeto_empresa)."""
    query = f"""
        SELECT id_projeto, empresa, porte, categoria, projeto
        FROM `{config.table_ref(config.TABLE_PROJETOS)}`
        WHERE id_projeto = @id_projeto
        LIMIT 1
    """
    job_config = _params([
        bigquery.ScalarQueryParameter("id_projeto", "STRING", id_projeto),
    ])
    for r in get_client().query(query, job_config=job_config).result():
        return {
            "id_projeto": r.id_projeto,
            "empresa": r.empresa,
            "porte": r.porte,
            "categoria": r.categoria,
            "projeto": r.projeto,
        }
    return None


def ja_avaliado(id_projeto: str, jurado: str) -> bool:
    """Trava anti-duplicado: True se já existe avaliação desse jurado para o projeto."""
    query = f"""
        SELECT COUNT(*) AS n
        FROM `{config.table_ref(config.TABLE_AVALIACOES)}`
        WHERE id_projeto = @id_projeto AND avaliador = @jurado
    """
    job_config = _params([
        bigquery.ScalarQueryParameter("id_projeto", "STRING", id_projeto),
        bigquery.ScalarQueryParameter("jurado", "STRING", jurado),
    ])
    for r in get_client().query(query, job_config=job_config).result():
        return r.n > 0
    return False


def contar_projetos() -> int:
    query = f"SELECT COUNT(*) AS n FROM `{config.table_ref(config.TABLE_PROJETOS)}`"
    for r in get_client().query(query).result():
        return r.n
    return 0


def contar_avaliados(jurado: str) -> int:
    query = f"""
        SELECT COUNT(DISTINCT id_projeto) AS n
        FROM `{config.table_ref(config.TABLE_AVALIACOES)}`
        WHERE avaliador = @jurado
    """
    job_config = _params([
        bigquery.ScalarQueryParameter("jurado", "STRING", jurado),
    ])
    for r in get_client().query(query, job_config=job_config).result():
        return r.n
    return 0


# --- Gravação (append-only) ----------------------------------------------

def inserir_avaliacao(id_projeto: str, avaliador: str, notas: dict[str, float],
                      comentario: str) -> None:
    """INSERT de uma nova avaliação. `notas` tem as 4 chaves de critério.

    Gera id_avaliacao (UUID), soma o total e carimba data_hora no fuso de SP.
    Usa DML INSERT (não streaming) para a linha ficar consultável de imediato.
    """
    total = sum(notas.values())
    query = f"""
        INSERT INTO `{config.table_ref(config.TABLE_AVALIACOES)}`
          (id_avaliacao, id_projeto, avaliador, planejamento_e_gestao,
           criatividade_inovacao, melhoria_continua, resultados_do_projeto,
           total, comentario, data_hora)
        VALUES
          (@id_avaliacao, @id_projeto, @avaliador, @planejamento,
           @criatividade, @melhoria, @resultados, @total, @comentario, @data_hora)
    """
    job_config = _params([
        bigquery.ScalarQueryParameter("id_avaliacao", "STRING", str(uuid.uuid4())),
        bigquery.ScalarQueryParameter("id_projeto", "STRING", id_projeto),
        bigquery.ScalarQueryParameter("avaliador", "STRING", avaliador),
        bigquery.ScalarQueryParameter("planejamento", "FLOAT64", notas["planejamento_e_gestao"]),
        bigquery.ScalarQueryParameter("criatividade", "FLOAT64", notas["criatividade_inovacao"]),
        bigquery.ScalarQueryParameter("melhoria", "FLOAT64", notas["melhoria_continua"]),
        bigquery.ScalarQueryParameter("resultados", "FLOAT64", notas["resultados_do_projeto"]),
        bigquery.ScalarQueryParameter("total", "FLOAT64", total),
        bigquery.ScalarQueryParameter("comentario", "STRING", comentario),
        bigquery.ScalarQueryParameter("data_hora", "TIMESTAMP", _agora_sp()),
    ])
    get_client().query(query, job_config=job_config).result()
    logger.info("Avaliação inserida: projeto=%s avaliador=%s total=%.1f",
                id_projeto, avaliador, total)
