#!/usr/bin/env bash
# =====================================================================
# Fase 0 — conta de serviço dedicada com PRIVILÉGIO MÍNIMO.
# Rode autenticado como owner do projeto (gcloud auth login).
# Requer: gcloud CLI + permissão para criar service accounts e IAM bindings.
# =====================================================================
set -euo pipefail

PROJECT="iptc-banco-de-dados"
DATASET="premio_esg_setcepar_2026"
SA_NAME="premio-esg-setcepar-site"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
KEY_FILE="premio-esg-setcepar-site-key.json"   # NÃO versionar — coberto pelo .gitignore (*.json)

gcloud config set project "${PROJECT}"

# 1) Criar a conta de serviço
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="Prêmio ESG SETCEPAR — app (Cloud Run)"

# 2) BigQuery Job User no PROJETO (necessário para rodar queries/DML)
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.jobUser"

# 3) BigQuery Data Editor RESTRITO AO DATASET do prêmio (privilégio mínimo).
#    Não usamos um role de projeto inteiro para limitar o alcance.
#    Pré-requisito: o dataset já deve existir — rode scripts/ddl.sql ANTES deste script.
if ! bq show "${PROJECT}:${DATASET}" >/dev/null 2>&1; then
  echo "ERRO: dataset ${PROJECT}:${DATASET} não existe. Rode a DDL antes:" >&2
  echo "  bq query --use_legacy_sql=false --project_id=${PROJECT} < scripts/ddl.sql" >&2
  exit 1
fi

# Detecta o binário Python (no Git Bash do Windows costuma ser 'python', não 'python3').
PYBIN="$(command -v python3 || command -v python || true)"
if [[ -z "${PYBIN}" ]]; then
  echo "ERRO: precisa de 'python3' ou 'python' no PATH para ajustar o IAM do dataset." >&2
  exit 1
fi

TMP_POLICY="$(mktemp)"
bq show --format=prettyjson "${PROJECT}:${DATASET}" > "${TMP_POLICY}"
"${PYBIN}" - "${TMP_POLICY}" "${SA_EMAIL}" <<'PY'
import json, sys
path, sa = sys.argv[1], sys.argv[2]
with open(path) as f:
    meta = json.load(f)
access = meta.get("access", [])
member = f"serviceAccount:{sa}"
if not any(e.get("role") == "WRITER" and e.get("userByEmail") == sa for e in access):
    access.append({"role": "WRITER", "userByEmail": sa})
meta["access"] = access
with open(path, "w") as f:
    json.dump(meta, f)
print("Acesso WRITER adicionado ao dataset para", sa)
PY
bq update --source "${TMP_POLICY}" "${PROJECT}:${DATASET}"
rm -f "${TMP_POLICY}"

# 4) Gerar a chave JSON (guardar FORA do repositório)
gcloud iam service-accounts keys create "${KEY_FILE}" \
  --iam-account="${SA_EMAIL}"

echo
echo "Pronto. Chave gerada em: ${KEY_FILE}"
echo "Aponte GOOGLE_APPLICATION_CREDENTIALS para esse arquivo no .env (NÃO versione)."
echo "Para o Cloud Run, prefira anexar a SA ao serviço (--service-account=${SA_EMAIL}) em vez da chave."
