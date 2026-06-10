-- =====================================================================
-- Fase 0 — DDL do ambiente NOVO (paralelo ao legado)
-- Projeto:  iptc-banco-de-dados
-- Dataset:  premio_esg_setcepar_2026
--
-- Como rodar (gcloud/bq CLI autenticado com a conta de serviço nova):
--   bq query --use_legacy_sql=false --project_id=iptc-banco-de-dados < scripts/ddl.sql
--
-- IMPORTANTE: o dataset/tabelas LEGADOS não são tocados aqui. Eles só serão
-- descomissionados na Fase 6, após os testes de fumaça (ver ROADMAP §3.1).
-- =====================================================================

-- Location igual à do dataset legado (premio_esg_setcepar_2025): southamerica-east1.
CREATE SCHEMA IF NOT EXISTS `iptc-banco-de-dados.premio_esg_setcepar_2026`
OPTIONS (location = 'southamerica-east1');

-- Usuários (somente leitura pelo app; lida no startup) ------------------
CREATE TABLE IF NOT EXISTS `iptc-banco-de-dados.premio_esg_setcepar_2026.usuarios` (
  username    STRING NOT NULL,   -- identificador de login (único)
  senha_hash  STRING NOT NULL,   -- hash werkzeug.security (PBKDF2) — nunca texto puro
  nome_jurado STRING NOT NULL,   -- nome exibido / usado como `avaliador`
  ativo       BOOL   NOT NULL    -- permite desativar sem apagar
);

-- Projetos (catálogo; somente leitura pelo app) -------------------------
CREATE TABLE IF NOT EXISTS `iptc-banco-de-dados.premio_esg_setcepar_2026.projetos` (
  id_projeto STRING NOT NULL,    -- identificador estável (PK lógica)
  empresa    STRING NOT NULL,    -- nome da empresa
  porte      STRING NOT NULL,    -- 'Micro/Pequenas' ou 'Médias/Grandes'
  categoria  STRING NOT NULL,    -- uma das 3 categorias
  projeto    STRING NOT NULL     -- nome/descrição do projeto submetido
);

-- Avaliações (append-only; o app só faz INSERT) -------------------------
CREATE TABLE IF NOT EXISTS `iptc-banco-de-dados.premio_esg_setcepar_2026.avaliacoes` (
  id_avaliacao          STRING    NOT NULL,  -- UUID gerado pelo app
  id_projeto            STRING    NOT NULL,  -- FK lógica -> projetos.id_projeto
  avaliador             STRING    NOT NULL,  -- nome_jurado de quem avaliou
  planejamento_e_gestao FLOAT64,             -- nota 1–5
  criatividade_inovacao FLOAT64,             -- nota 1–5
  melhoria_continua     FLOAT64,             -- nota 1–5
  resultados_do_projeto FLOAT64,             -- nota 1–5
  total                 FLOAT64,             -- soma das 4 notas
  comentario            STRING,              -- obrigatório
  data_hora             TIMESTAMP            -- horário de São Paulo
);
