"""Verificação local: renderiza todas as telas com o BigQuery mockado.

Não conecta no BigQuery — substitui as funções de `app.bq` por stubs e usa o
test_client do Flask para garantir que templates e rotas funcionam ponta a ponta.
Rode: .venv/Scripts/python.exe scripts/_smoke_render.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FLASK_SECRET_KEY", "teste-secret")

from app import bq, auth, main  # noqa: E402

# --- Stubs do BigQuery -----------------------------------------------------
PROJETO = {"id_projeto": "proj-001", "empresa": "Empresa Fictícia 01",
           "porte": "Micro/Pequenas", "categoria": "Responsabilidade Ambiental",
           "projeto": "Projeto fictício 01"}

bq.contar_projetos = lambda: 18
bq.contar_avaliados = lambda jurado: 3
bq.carregar_projetos_pendentes = lambda j: [PROJETO, {"id_projeto": "proj-002", "empresa": "Empresa Fictícia 02", "porte": "Médias/Grandes", "categoria": "Responsabilidade Social", "projeto": "Projeto 02"}]
bq.obter_projeto = lambda i: PROJETO if i == "proj-001" else None
bq.ja_avaliado = lambda i, j: False
inseridas = []
bq.inserir_avaliacao = lambda i, j, notas, c: inseridas.append((i, j, notas, c))
auth._usuarios = {"jurado_1": {"senha": "x", "nome_jurado": "Jurado Um"}}

app = main.app
app.config["WTF_CSRF_ENABLED"] = False  # facilita o POST no teste
client = app.test_client()


def check(resp, esperado, rotulo):
    assert resp.status_code == esperado, f"{rotulo}: status {resp.status_code} (esperava {esperado})"
    print(f"  OK  {rotulo} -> {resp.status_code}")


# 1) Login (GET)
check(client.get("/"), 200, "GET / (login)")

# Sessão logada para as próximas telas
def set_step(**kv):
    with client.session_transaction() as s:
        s.clear()
        s["username"] = "jurado_1"
        s["jurado"] = "Jurado Um"
        s.update(kv)

# 2) Tela 1 — seleção (sem projeto selecionado na sessão)
set_step()
check(client.get("/avaliacao"), 200, "avaliacao tela 1 (seleção)")

# 3) Tela 2 — formulário de notas (projeto selecionado)
set_step(id_projeto_selecionado="proj-001")
check(client.get("/avaliacao"), 200, "avaliacao tela 2 (notas)")

# 6) Salvar avaliação (POST)
resp = client.post("/avaliacao", data={
    "acao": "salvar_avaliacao",
    "planejamento_e_gestao": "5", "criatividade_inovacao": "4",
    "melhoria_continua": "3", "resultados_do_projeto": "5",
    "comentario": "Bom projeto.",
})
check(resp, 302, "POST salvar (redirect)")
assert inseridas and inseridas[0][0] == "proj-001", "INSERT não foi chamado"
assert inseridas[0][2] == {"planejamento_e_gestao": 5.0, "criatividade_inovacao": 4.0,
                           "melhoria_continua": 3.0, "resultados_do_projeto": 5.0}, "notas erradas"
print(f"  OK  inserir_avaliacao chamado: {inseridas[0][:2]} total={sum(inseridas[0][2].values())}")

# 7) Comentário vazio é rejeitado
inseridas.clear()
set_step(id_projeto_selecionado="proj-001")  # salvar anterior limpou a seleção
resp = client.post("/avaliacao", data={
    "acao": "salvar_avaliacao",
    "planejamento_e_gestao": "5", "criatividade_inovacao": "4",
    "melhoria_continua": "3", "resultados_do_projeto": "5", "comentario": "   ",
})
check(resp, 302, "POST comentário vazio (redirect)")
assert not inseridas, "não deveria inserir com comentário vazio"
print("  OK  comentário vazio bloqueado")

print("\nTODOS OS CHECKS PASSARAM.")
