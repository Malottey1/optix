# Optix: build the dashboard with Node, run the API (service/app.py) on slim Python as a non-root user.
# Build:  docker build -t optix:local .        Run:  docker compose up   (http://127.0.0.1:8000/#/live)
# No secrets in the image: Azure settings come from the environment at run time.

FROM node:22.20.0-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --ignore-scripts
COPY web/ ./
COPY contracts/personalization.json /contracts/personalization.json
RUN npm run build

FROM python:3.13.7-slim-bookworm AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements-azure.txt ./
RUN pip install -r requirements-azure.txt
COPY agents/ agents/
COPY engine/ engine/
COPY contracts/ contracts/
COPY data_gen/ data_gen/
COPY service/ service/
COPY data/showcase/ data/showcase/
COPY data/phrasing-cache/ data/phrasing-cache/
COPY --from=web /web/dist web/dist
COPY web/public/data web/public/data
RUN useradd --create-home --uid 10001 optix && chown -R optix /app/data
USER optix
ENV OPTIX_DATA_DIR=/app/web/public/data OPTIX_WEB_DIST=/app/web/dist
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
