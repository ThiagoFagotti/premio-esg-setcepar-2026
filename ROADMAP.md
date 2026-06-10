# ROADMAP — Sistema Prêmio ESG SETCEPAR (refatoração)

> **Para quem vai executar:** este arquivo é autossuficiente. Ele contém o contexto do
> sistema, as decisões de arquitetura já fechadas e a lista ordenada de tarefas.
> Execute fase a fase, na ordem. **Não reabra decisões já tomadas** — elas foram
> debatidas e estão registradas aqui. Se algo estiver marcado como `[PREENCHER]`,
> peça o valor ao responsável antes de codar aquela parte.

---

## 1. Contexto do sistema

Aplicação **Flask** (Python) onde jurados avaliam projetos de empresas no **Prêmio ESG
SETCEPAR**. Deploy via **Docker + Gunicorn** no **Google Cloud Run**. Os dados ficam no
**BigQuery** (projeto `iptc-banco-de-dados`).

Fluxo do jurado: login → escolhe **Categoria** → escolhe **Porte** → escolhe **Empresa**
→ atribui 4 notas (1 a 5) + comentário → salva. Uma avaliação salva **não pode ser
editada**.

Estado atual do código (antes desta refatoração): tudo em um único `app/main.py` (~431
linhas), com usuários/senhas hardcoded, gravação via `UPDATE` no BigQuery, e uma
categoria especial "Atitude ESG". Esta refatoração reescreve a base sobre um modelo de
dados novo. **Nós criamos todos os dados do zero** — não há base legada a preservar.

---

## 2. Decisões de arquitetura (fechadas — não reabrir)

1. **Continuar no BigQuery** por enquanto (não migrar para outro banco).
2. **Gravação append-only via `INSERT`** numa tabela de avaliações. **Eliminar todo
   `UPDATE`** e o campo `situacao`. "Já avaliado" passa a ser computado por `LEFT JOIN`.
3. **Separar dados em 3 tabelas**: `usuarios`, `projetos`, `avaliacoes` (esquemas na §3).
4. **Todos os jurados avaliam todos os projetos.** Não há tabela de atribuição.
5. **Usuários/senhas no BigQuery**, senha **em texto puro** (decisão institucional revista —
   app interno pequeno; o hash foi removido). A lista é
   **lida uma vez no startup** do app (login validado em memória).
6. **Remover o conceito de "admin".** Logins de teste se comportam como jurados normais.
   A parte administrativa (apuração, ranking) é feita **direto no BigQuery**, fora do app.
7. **Remover a categoria "Atitude ESG"** (decisão do SETCEPAR): rota, template, função e
   tabela associada saem do projeto.
8. **Avaliação não é editável.** Regra: **a primeira resposta vence**; trava anti-duplicado
   no servidor.
9. **Porte entra no fluxo do jurado.** A separação por porte existe porque projetos de
   portes diferentes **não competem entre si** — a premiação é por par `(categoria, porte)`.
   - Categorias (3): `Responsabilidade Ambiental`, `Responsabilidade Social`,
     `Governança Corporativa`.
   - Portes (2): `Micro/Pequenas`, `Médias/Grandes`.
   - Logo: **3 × 2 = 6 trilhas de premiação**. A agregação/ranking dessas trilhas é
     feita no BigQuery (fora do app).
10. **Progresso**: exibir apenas o **total geral** do jurado ("X de Y avaliados").
11. **Confirmação antes de salvar** uma avaliação.
12. **Cache do preenchimento no navegador** (localStorage), para não perder notas/comentário
    num reload acidental antes de salvar.
13. **Repositório novo** + **conta de serviço dedicada com privilégio mínimo**.
14. **Subir a qualidade geral do código** (logging, config, timezone, imports, etc.).

### Fora de escopo (não fazer)
- Migrar para fora do BigQuery.
- Permitir edição de avaliações.
- Construir telas administrativas / apuração / ranking (feito no BQ).
- Implementar a lógica de "premiar 2x por porte" no app (é agregação BQ-side).

---

## 3. Modelo de dados alvo (BigQuery)

Projeto: `iptc-banco-de-dados`
Dataset: `premio_esg_setcepar_2026` (dataset único, novo; o antigo
`premio_esg_setcepar_2025` da Atitude ESG é descontinuado **apenas na Fase 6**).

### Tabela `usuarios` (somente leitura pelo app; lida no startup)
| coluna       | tipo   | observações                                  |
|--------------|--------|----------------------------------------------|
| `username`   | STRING | identificador de login (único)               |
| `senha`      | STRING | senha em texto puro (app interno; sem hash)   |
| `nome_jurado`| STRING | nome exibido / usado como `avaliador`         |
| `ativo`      | BOOL   | permite desativar sem apagar                 |

### Tabela `projetos` (catálogo; somente leitura pelo app)
| coluna       | tipo   | observações                                            |
|--------------|--------|--------------------------------------------------------|
| `id_projeto` | STRING | identificador estável (PK lógica)                      |
| `empresa`    | STRING | nome da empresa                                        |
| `porte`      | STRING | `Micro/Pequenas` ou `Médias/Grandes`                   |
| `categoria`  | STRING | uma das 3 categorias                                   |
| `projeto`    | STRING | nome/descrição do projeto submetido                    |

> Porte é atributo da empresa; a mesma empresa pode ter projetos em várias categorias,
> sempre com o mesmo porte.

### Tabela `avaliacoes` (append-only; o app só faz `INSERT`)
| coluna                  | tipo      | observações                              |
|-------------------------|-----------|------------------------------------------|
| `id_avaliacao`          | STRING    | UUID gerado pelo app                     |
| `id_projeto`            | STRING    | FK lógica → `projetos.id_projeto`        |
| `avaliador`             | STRING    | `nome_jurado` de quem avaliou            |
| `planejamento_e_gestao` | FLOAT64   | nota 1–5                                 |
| `criatividade_inovacao` | FLOAT64   | nota 1–5                                 |
| `melhoria_continua`     | FLOAT64   | nota 1–5                                 |
| `resultados_do_projeto` | FLOAT64   | nota 1–5                                 |
| `total`                 | FLOAT64   | soma das 4 notas                         |
| `comentario`            | STRING    | obrigatório                              |
| `data_hora`             | TIMESTAMP | horário de São Paulo                     |

### Consultas-chave
**Projetos a avaliar** (de um jurado, numa categoria+porte):
```sql
SELECT p.id_projeto, p.empresa, p.projeto
FROM `PROJ.DATASET.projetos` p
LEFT JOIN `PROJ.DATASET.avaliacoes` a
  ON a.id_projeto = p.id_projeto AND a.avaliador = @jurado
WHERE p.categoria = @categoria AND p.porte = @porte AND a.id_projeto IS NULL
ORDER BY p.empresa
```
**Progresso** (total geral do jurado):
```sql
-- denominador: total de projetos no catálogo
SELECT COUNT(*) FROM `PROJ.DATASET.projetos`;
-- numerador: projetos distintos já avaliados pelo jurado
SELECT COUNT(DISTINCT id_projeto) FROM `PROJ.DATASET.avaliacoes` WHERE avaliador = @jurado;
```
**Trava anti-duplicado** (antes do INSERT): rejeitar se já existir linha para
`(id_projeto, avaliador)`.

---

## 3.1. Estratégia de ambiente paralelo (sem risco ao sistema atual)

Toda a refatoração roda em **paralelo** ao sistema em produção, para que um fracasso não
afete nada e o rollback seja trivial:

- **Dataset novo** (`premio_esg_setcepar_2026`) com as 3 tabelas novas. O **dataset atual permanece
  intocado** — o código novo nunca escreve nele.
- **Repositório novo** e **deploy separado** (novo serviço/revisão no Cloud Run). O deploy
  antigo continua no ar até a validação terminar.
- **Plano de rollback:** se a nova versão falhar, basta voltar a usar o **código antigo +
  dataset antigo** — nenhum dado novo foi gravado sobre o ambiente legado.
- **Só descomissionar o ambiente antigo (incl. dataset da Atitude ESG) na Fase 6**, depois
  dos testes de fumaça passarem. **Nunca antes.**

---

## 4. Plano de execução (fases ordenadas)

### Fase 0 — Infra, dados e repositório (manual + DDL)  ✅ CONCLUÍDA — executada manualmente pelo Console do GCP (conta de serviço, dataset, tabelas e seed fictício)
- [x] Criar **repositório novo** e `git init`. Reaproveitar o `.gitignore` atual (já cobre
      `.env` e `*.json`). Garantir que **nenhum segredo** entre no histórico.  ✅ feito (`git init`; `.gitignore` cobre `.env`/`*.json`/`.venv`; nada de segredo staged)
- [x] **Conta de serviço dedicada** `premio-esg-setcepar-site@iptc-banco-de-dados.iam.gserviceaccount.com`
      com **privilégio mínimo**: `BigQuery Job User` (projeto) + `BigQuery Data Editor`
      **restrito ao dataset** do prêmio. Criada **manualmente pelo Console**; chave JSON fora do repo,
      usada **só no dev local** (em produção a SA é anexada ao Cloud Run, sem chave).  ✅
- [x] **Dataset** `premio_esg_setcepar_2026` + as 3 tabelas (§3), criados pelo Console.
      **Location `southamerica-east1`** (mesma do dataset legado).  ✅
- [x] **`usuarios`** populada com 5 jurados placeholder `jurado_1`..`jurado_5` (senhas provisórias,
      senha em texto puro; trocáveis depois via `UPDATE` na tabela `usuarios`).  ✅
- [x] **`projetos`** semeada com **18 projetos fictícios** (3 categorias × 2 portes × 3) para
      desenvolver/testar. Os dados reais (~35) **virão do SETCEPAR** (ver §5).  ✅

> O dataset/tabelas antigos **não são tocados** nesta fase — só serão descomissionados na
> Fase 6, após a validação (ver §3.1, estratégia de ambiente paralelo).

### Fase 1 — Configuração e base do app  ✅ CONCLUÍDA (`app/config.py`, `app/bq.py`, `requirements.txt`)
- [x] Centralizar configuração: `.env` deve conter e o app deve **realmente usar**
      `BIGQUERY_PROJECT_ID`, dataset e nomes de tabela, `FLASK_SECRET_KEY`,
      `GOOGLE_APPLICATION_CREDENTIALS`. **Remover variáveis mortas** (hoje `BIGQUERY_*`
      existem no `.env` mas não são lidas; o nome da tabela está hardcoded em `main.py:32`).
- [x] `FLASK_SECRET_KEY` **obrigatória** — sem o fallback inseguro
      `'default_secret_key_for_dev'` (`main.py:20`). Falhar de forma clara se ausente.
- [x] Inicialização segura do cliente BigQuery (não quebrar no import; hoje
      `client = get_bigquery_client()` roda em tempo de import, `main.py:31`).
- [x] Trocar todos os `print(...)` de debug pelo módulo `logging`.
- [x] **Timezone correto**: usar `zoneinfo`/`America/Sao_Paulo` em vez de
      `datetime.now() - timedelta(hours=3)` (`main.py:167,206,235`). Remover `import pytz`
      não usado e os **imports duplicados de `datetime`** (`main.py:5,9,10`).
- [x] **Fixar versões** no `requirements.txt` (hoje sem pins).

### Fase 2 — Autenticação via BigQuery  ✅ CONCLUÍDA (`app/auth.py`; CSRF via Flask-WTF em `main.py`)
- [x] Carregar `usuarios` da tabela **no startup** para memória (estrutura: username →
      {senha, nome_jurado}). Considerar só usuários `ativo = TRUE`.
- [x] Validar login por **comparação direta da senha**. **Remover o dict hardcoded** (`main.py:35-42`).
- [x] **Remover o conceito de admin**: apagar o ramo "admin" morto em `carregar_*`
      (`main.py:64,103`) e tratar todos os logins igualmente.
- [x] Criar decorator `@login_required` e aplicá-lo (elimina os `if 'username' not in
      session` repetidos).
- [x] Adicionar **proteção CSRF** nos formulários POST (ex.: Flask-WTF ou token de sessão).

### Fase 3 — Remover Atitude ESG  ✅ CONCLUÍDA (rota/função/template removidos; categoria fora da lista)
- [x] Remover a rota `/avaliacao_atitude_esg` (`main.py:382-428`), a função
      `salvar_avaliacao_atitude_esg` (`main.py:204-259`) e o template
      `app/templates/avaliacao_atitude_esg.html`.
- [x] Remover o redirecionamento especial (`main.py:314-315`) e o item `"Atitude ESG"` da
      lista `CATEGORIAS` (`main.py:45-50`). Categorias finais = as 3.

### Fase 4 — Novo fluxo (porte) e gravação append-only  ✅ CONCLUÍDA (fluxo 3 etapas + `INSERT` com trava anti-duplicado)
- [x] Definir constantes `CATEGORIAS` (3) e `PORTES` (`Micro/Pequenas`, `Médias/Grandes`).
- [x] Fluxo de seleção em **página única** (cascata Categoria → Porte → Empresa filtrada no
      navegador) — revisão de UX posterior ao plano, que previa 3 etapas separadas. Na sessão
      guarda-se só `id_projeto_selecionado` (seleção = "Tela 1"; formulário de notas = "Tela 2").
- [x] `carregar_projetos_pendentes(jurado)` (LEFT JOIN da §3, todos os portes/categorias) alimenta
      a cascata numa única consulta.
- [x] Substituir `atualizar_avaliacao` (UPDATE, `main.py:164-201`) por uma função de
      **`INSERT` em `avaliacoes`** (gerar `id_avaliacao` UUID, `total` somado, `data_hora`
      no fuso de SP).
- [x] **Trava anti-duplicado** server-side antes do INSERT (e a empresa já some da lista
      via o LEFT JOIN).
- [x] Obter a descrição do projeto direto do catálogo `projetos` (substitui
      `obter_projeto_empresa`, `main.py:136-161`).

### Fase 5 — UX  ✅ CONCLUÍDA (progresso, confirmação, cache localStorage, `base.html` + CSS estático)
- [x] **Progresso total** ("X de Y avaliados") **apenas na tela de seleção** (some na tela de notas) — query da §3.
- [x] **Confirmação antes de salvar** (modal/`confirm` antes do submit final).
- [x] **Cache localStorage** do preenchimento em andamento, chaveado por `id_projeto`;
      restaurar ao abrir, limpar após salvar com sucesso.
- [x] Criar **template base** compartilhado e mover o **CSS para arquivo estático**,
      eliminando a duplicação entre os templates (hoje todo o CSS é inline e repetido).

### Fase 6 — Deploy e validação  ⏳ PENDENTE (próximo passo) — código pronto e testado localmente; falta publicar no Cloud Run e validar
- [x] Gunicorn no `Dockerfile` com `--workers 2 --threads 8 --timeout 120`, ligando em `$PORT`
      (Cloud Run), base `python:3.12-slim`. **`.dockerignore`** criado p/ a chave/`.env` não
      entrarem na imagem.  ✅
- [ ] Deploy como **serviço novo** `premio-esg-setcepar-2026` no Cloud Run (`southamerica-east1`),
      via Console **"Deploy from source"** (build pelo Dockerfile, a partir do repositório Git).
      **Conta anexada** `premio-esg-setcepar-site@...` (sem chave). Env vars: `FLASK_SECRET_KEY`
      (novo/forte), `BIGQUERY_PROJECT_ID`, `BIGQUERY_DATASET`; **não** definir
      `GOOGLE_APPLICATION_CREDENTIALS`. **Allow unauthenticated** (o login é do app). Passo a passo no `README.md`.
- [ ] **Testes de fumaça** na URL nova: login (sucesso e falha); avaliar em cada `(categoria, porte)`;
      o projeto some da lista após salvar; trava anti-duplicado; progresso correto; logout.
- [ ] **Só após os testes passarem:** apontar tráfego/domínio para a versão nova e
      **descomissionar o ambiente antigo** (código + dataset legado, incl. Atitude ESG).
      Se algo falhar, manter o antigo e reverter (ver §3.1).

---

## 5. Dados definidos e pendências

### Definido
- **Dataset:** `premio_esg_setcepar_2026` (projeto `iptc-banco-de-dados`).
- **Jurados:** 5 usuários placeholder `jurado_1`..`jurado_5` (nomes reais a definir; a banca
  ainda vai mudar). Senha individual por jurado, provisória, trocável depois.
- **Portes:** `Micro/Pequenas` e `Médias/Grandes` (grafia exata, com barra e acento).
- **Categorias:** `Responsabilidade Ambiental`, `Responsabilidade Social`,
  `Governança Corporativa`.
- **Volume esperado:** ~35 projetos (referência da edição anterior). Uma empresa pode
  submeter **um ou mais** projetos.

### Pendências (não bloqueiam o desenvolvimento — usar dados fictícios até chegarem)
- ⏳ **Nomes e senhas reais dos jurados** — virão quando a banca for definida.
- ⏳ **Lista real de projetos** (`empresa`, `porte`, `categoria`, `projeto`) — **virá do
  SETCEPAR**. Reaproveitar as colunas da tabela anterior como base, **acrescentando**
  `porte` (coluna nova) e `id_projeto` (gerado por nós). Até lá, semear `projetos` com
  dados fictícios cobrindo as 3 categorias × 2 portes para testar o fluxo completo.
- ⏳ **Antes de abrir aos jurados reais:** substituir jurados/projetos fictícios pelos reais e
  **limpar a tabela `avaliacoes`** (apagar as avaliações de teste geradas na validação).
- ℹ️ **Dev local (gotcha):** rodar `pip install -r requirements.txt` no venv — o `tzdata` é
  obrigatório (no Windows e na imagem `slim`) ou o `INSERT` falha ao carimbar o fuso de SP.
