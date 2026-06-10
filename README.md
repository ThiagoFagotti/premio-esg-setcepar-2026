# Sistema Prêmio ESG SETCEPAR

Aplicação Flask onde jurados avaliam projetos do Prêmio ESG SETCEPAR. Deploy via
Docker + Gunicorn no Google Cloud Run; dados no BigQuery (`iptc-banco-de-dados`).

Fluxo do jurado: **login → Categoria → Porte → Empresa → 4 notas (1–5) + comentário → salvar**.
Gravação é **append-only** (`INSERT`); uma avaliação salva **não pode ser editada**
(a primeira resposta vence; trava anti-duplicado no servidor).

## Estrutura

```
app/
  config.py     # configuração lida do .env (falha claro se faltar algo)
  bq.py         # acesso ao BigQuery (queries + INSERT append-only)
  auth.py       # login via tabela usuarios (hash) + decorator login_required
  main.py       # app Flask + rotas
  templates/    # base.html, login.html, avaliacao.html
  static/css/   # style.css (CSS compartilhado, antes inline/duplicado)
scripts/
  ddl.sql        # cria dataset + 3 tabelas
  seed.py        # popula usuarios (placeholder) + projetos (fictícios)
  gen_hash.py    # gera hash de senha para colar em usuarios
  infra_setup.sh # cria a conta de serviço com privilégio mínimo
```

## Modelo de dados (BigQuery)

Projeto `iptc-banco-de-dados`, dataset `premio_esg_setcepar_2026`, tabelas
`usuarios`, `projetos`, `avaliacoes` (esquemas em [scripts/ddl.sql](scripts/ddl.sql)).

## Setup local

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # preencha FLASK_SECRET_KEY e o caminho da chave
python -m app.main          # http://localhost:5000
```

## Fase 0 — Infra (rodar uma vez, com credenciais GCP)

```bash
# Ordem importa: o dataset precisa existir ANTES de conceder acesso à conta de serviço.
bq query --use_legacy_sql=false --project_id=iptc-banco-de-dados < scripts/ddl.sql   # cria dataset + 3 tabelas
bash scripts/infra_setup.sh                                   # conta de serviço + IAM mínimo (concede WRITER no dataset)
python scripts/seed.py                                        # dados fictícios p/ desenvolver
```

> O dataset/tabelas **legados não são tocados**. Só serão descomissionados na Fase 6,
> após os testes de fumaça (ROADMAP §3.1 — ambiente paralelo, rollback trivial).

## Fase 6 — Deploy (Cloud Run, serviço novo separado)

Serviço **novo** `premio-esg-setcepar-2026`, em paralelo ao antigo (que segue no ar).
Credencial via **conta de serviço anexada** (sem chave JSON no contêiner).

### Opção A — Console (navegador, sem gcloud local)
1. Cloud Run → **Create Service** → **"Continuously deploy from a repository" → Set up with Cloud Build**;
   conecte o repositório Git e o branch. **Build type: Dockerfile** (pode pedir p/ habilitar as APIs
   Cloud Build / Artifact Registry).
2. **Region:** `southamerica-east1`. **Authentication:** *Allow unauthenticated* (o login é do app).
3. **Security → Service account:** `premio-esg-setcepar-site@iptc-banco-de-dados.iam.gserviceaccount.com`.
4. **Variables & Secrets:** `FLASK_SECRET_KEY` (novo/forte), `BIGQUERY_PROJECT_ID=iptc-banco-de-dados`,
   `BIGQUERY_DATASET=premio_esg_setcepar_2026`. **Não** definir `GOOGLE_APPLICATION_CREDENTIALS`.
5. **Create** → gera uma URL própria; o serviço antigo continua intacto na URL dele.

### Opção B — gcloud (ex.: Cloud Shell)
```bash
gcloud run deploy premio-esg-setcepar-2026 \
  --source . \
  --region southamerica-east1 \
  --allow-unauthenticated \
  --service-account premio-esg-setcepar-site@iptc-banco-de-dados.iam.gserviceaccount.com \
  --set-env-vars FLASK_SECRET_KEY=...,BIGQUERY_PROJECT_ID=iptc-banco-de-dados,BIGQUERY_DATASET=premio_esg_setcepar_2026
```

### Testes de fumaça (antes de apontar o tráfego)

- [ ] Login com credencial válida e com credencial inválida.
- [ ] Avaliar um projeto em cada `(categoria, porte)` — 6 trilhas.
- [ ] O projeto **some da lista** após salvar.
- [ ] Tentar avaliar o mesmo projeto de novo → bloqueado (trava anti-duplicado).
- [ ] Progresso "X de Y" correto.
- [ ] Logout encerra a sessão.

**Só após passar:** apontar 100% do tráfego para a versão nova e descomissionar o
ambiente antigo (código + dataset legado, incl. Atitude ESG). Se algo falhar,
manter o antigo e reverter.

## Pendências (ROADMAP §5 — não bloqueiam o desenvolvimento)

- Nomes e senhas reais dos jurados (substituir os placeholders `jurado_1..5`).
- Lista real de projetos do SETCEPAR (substituir os fictícios do `seed.py`).
