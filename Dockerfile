# Benefits 360 — uma instância. Volume persistente em NEWPORT_VOLUME_DIR.
# Segredos só no painel da plataforma, nunca neste arquivo.

FROM node:22-alpine AS front
WORKDIR /front
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_FAIXA_RASCUNHO=1
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY \
    VITE_FAIXA_RASCUNHO=$VITE_FAIXA_RASCUNHO
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    NEWPORT_WEB_DIST=/app/web/dist
COPY pyproject.toml ./
COPY src ./src
COPY docs ./docs
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[app]"
COPY --from=front /front/dist ./web/dist
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request; p=os.environ.get('PORT','8000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/api/saude')"
CMD ["python", "-m", "newport_app.hosted_start"]
