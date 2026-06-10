"""Aplicação Flask — Prêmio ESG SETCEPAR (refatoração ROADMAP).

Fluxo do jurado: login -> Categoria -> Porte -> Empresa -> 4 notas + comentário
-> salvar (INSERT append-only). Uma avaliação salva não pode ser editada
(a primeira resposta vence; trava anti-duplicado no servidor).
"""
import logging

from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for)
from flask_wtf.csrf import CSRFProtect

from . import auth, bq, config
from .auth import login_required

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = config.SECRET_KEY
csrf = CSRFProtect(app)  # proteção CSRF em todos os POST

# Os 4 critérios de nota (1–5).
NOTA_CAMPOS = [
    "planejamento_e_gestao",
    "criatividade_inovacao",
    "melhoria_continua",
    "resultados_do_projeto",
]


@app.route("/", methods=["GET", "POST"])
def login():
    if "username" in session:
        return redirect(url_for("avaliacao"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        usuario = auth.autenticar(username, password)
        if usuario:
            session.clear()
            session["username"] = username
            session["jurado"] = usuario["nome_jurado"]
            logger.info("Login bem-sucedido: %s", username)
            return redirect(url_for("avaliacao"))
        logger.warning("Login falhou para username=%s", username)
        flash("Usuário ou senha incorretos.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/avaliacao", methods=["GET", "POST"])
@login_required
def avaliacao():
    jurado = session["jurado"]

    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "selecionar_projeto":
            session["id_projeto_selecionado"] = request.form.get("id_projeto")
            return redirect(url_for("avaliacao"))
        if acao == "voltar":
            session.pop("id_projeto_selecionado", None)
            return redirect(url_for("avaliacao"))
        if acao == "salvar_avaliacao":
            return _salvar_avaliacao(jurado)

    return _render_etapa_atual(jurado)


def _render_etapa_atual(jurado: str):
    """Duas telas decididas pela sessão:

    - sem projeto selecionado -> Tela 1 (seleção em cascata + progresso);
    - com projeto selecionado -> Tela 2 (formulário de notas, sem progresso).
    """
    id_projeto = session.get("id_projeto_selecionado")
    projeto_atual = None
    if id_projeto:
        projeto_atual = bq.obter_projeto(id_projeto)
        if projeto_atual is None:  # id inválido/órfão na sessão
            session.pop("id_projeto_selecionado", None)

    em_selecao = projeto_atual is None
    return render_template(
        "avaliacao.html",
        jurado=jurado,
        categorias=config.CATEGORIAS,
        portes=config.PORTES,
        projetos_pendentes=bq.carregar_projetos_pendentes(jurado) if em_selecao else [],
        projeto_atual=projeto_atual,
        total_projetos=bq.contar_projetos() if em_selecao else 0,
        avaliados=bq.contar_avaliados(jurado) if em_selecao else 0,
        salvo=request.args.get("salvo"),
    )


def _salvar_avaliacao(jurado: str):
    id_projeto = session.get("id_projeto_selecionado")
    if not id_projeto:
        flash("Nenhum projeto selecionado.")
        return redirect(url_for("avaliacao"))

    try:
        notas = {campo: float(request.form[campo]) for campo in NOTA_CAMPOS}
    except (KeyError, ValueError):
        flash("Preencha as quatro notas.")
        return redirect(url_for("avaliacao"))

    if not all(1 <= n <= 5 for n in notas.values()):
        flash("As notas devem estar entre 1 e 5.")
        return redirect(url_for("avaliacao"))

    comentario = request.form.get("comentario", "").strip()
    if not comentario:
        flash("O comentário é obrigatório.")
        return redirect(url_for("avaliacao"))

    # Trava anti-duplicado (a primeira resposta vence).
    if bq.ja_avaliado(id_projeto, jurado):
        flash("Este projeto já foi avaliado por você e não pode ser reavaliado.")
        session.pop("id_projeto_selecionado", None)
        return redirect(url_for("avaliacao"))

    try:
        bq.inserir_avaliacao(id_projeto, jurado, notas, comentario)
    except Exception:
        logger.exception("Falha ao inserir avaliação (projeto=%s)", id_projeto)
        flash("Erro ao salvar avaliação. Tente novamente.")
        return redirect(url_for("avaliacao"))

    flash("Avaliação salva com sucesso!")
    session.pop("id_projeto_selecionado", None)
    # `salvo` permite ao front limpar o cache (localStorage) daquele projeto.
    return redirect(url_for("avaliacao", salvo=id_projeto))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
