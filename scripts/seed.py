"""Fase 0 — popula `usuarios` (placeholders) e `projetos` (fictícios) no dataset novo.

Uso:
    python scripts/seed.py

Lê as mesmas variáveis de ambiente do app (.env). Requer credenciais com
BigQuery Data Editor no dataset `premio_esg_setcepar_2026`.

As tabelas precisam existir antes (rode `scripts/ddl.sql` primeiro).
Usa load jobs (WRITE_APPEND), então as linhas ficam consultáveis imediatamente
(diferente de streaming inserts). Rode apenas uma vez para não duplicar.

ATENÇÃO: senhas placeholder — TROCAR antes de produção. Os nomes/senhas reais
dos jurados virão quando a banca for definida (ROADMAP §5).
"""
import os

from dotenv import load_dotenv
from google.cloud import bigquery
from werkzeug.security import generate_password_hash

load_dotenv()

PROJECT = os.environ.get("BIGQUERY_PROJECT_ID", "iptc-banco-de-dados")
DATASET = os.environ.get("BIGQUERY_DATASET", "premio_esg_setcepar_2026")


def ref(table: str) -> str:
    return f"{PROJECT}.{DATASET}.{table}"


# 5 jurados placeholder. Senha individual por jurado, provisória e trocável depois.
JURADOS = [
    ("jurado_1", "Jurado Um (placeholder)",    "esg-jurado1-2026"),
    ("jurado_2", "Jurado Dois (placeholder)",  "esg-jurado2-2026"),
    ("jurado_3", "Jurado Três (placeholder)",  "esg-jurado3-2026"),
    ("jurado_4", "Jurado Quatro (placeholder)","esg-jurado4-2026"),
    ("jurado_5", "Jurado Cinco (placeholder)", "esg-jurado5-2026"),
]

CATEGORIAS = [
    "Responsabilidade Ambiental",
    "Responsabilidade Social",
    "Governança Corporativa",
]
PORTES = ["Micro/Pequenas", "Médias/Grandes"]


def build_usuarios() -> list[dict]:
    return [
        {
            "username": username,
            "senha_hash": generate_password_hash(senha),
            "nome_jurado": nome,
            "ativo": True,
        }
        for (username, nome, senha) in JURADOS
    ]


def build_projetos() -> list[dict]:
    """3 projetos fictícios por par (categoria, porte) => 18 projetos cobrindo as 6 trilhas."""
    rows = []
    n = 0
    for categoria in CATEGORIAS:
        for porte in PORTES:
            for _ in range(3):
                n += 1
                rows.append({
                    "id_projeto": f"proj-{n:03d}",
                    "empresa": f"Empresa Fictícia {n:02d}",
                    "porte": porte,
                    "categoria": categoria,
                    "projeto": f"Projeto fictício {n:02d} — {categoria} ({porte})",
                })
    return rows


def load(client: bigquery.Client, table: str, rows: list[dict]) -> None:
    job = client.load_table_from_json(
        rows,
        ref(table),
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"),
    )
    job.result()
    print(f"  -> {len(rows)} linhas inseridas em {table}")


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    print(f"Populando dataset {DATASET}...")
    load(client, "usuarios", build_usuarios())
    load(client, "projetos", build_projetos())
    print("\nCredenciais placeholder (TROCAR antes de produção):")
    for (username, _, senha) in JURADOS:
        print(f"  {username} / {senha}")


if __name__ == "__main__":
    main()
