FROM python:3.12-slim

WORKDIR /app

# Saída de log sem buffer (importante para o Cloud Run / Cloud Logging)
ENV PYTHONUNBUFFERED=1

# Instalar dependências primeiro (cache de camadas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante da aplicação
COPY . .

EXPOSE 8080

# Gunicorn com parâmetros sãos (antes: --workers 1 --timeout 0).
# timeout finito evita workers presos; 2 workers x 8 threads atende o volume baixo.
# Liga na porta que o Cloud Run injeta via $PORT (default 8080 para rodar local).
CMD exec gunicorn --bind :${PORT:-8080} --workers 2 --threads 8 --timeout 120 app.main:app
