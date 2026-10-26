# Hosting the demo

The public demo is https://optixweb13588.z28.web.core.windows.net/, an Azure Storage static website
(account in France Central). It hosts the built dashboard and nothing else.

## Build and upload

```sh
cd web
npm ci
npm run build                      # vite build -> web/dist (base "./", hash routes: no server rewrites)
az storage blob upload-batch \
  --account-name optixweb13588 --auth-mode login \
  --destination '$web' --source dist --overwrite
```

`npm run build` bundles the committed data in `web/public/data`. To change that data, run
`npm run data` after regenerating `out/` with `agents.run_match` and `agents.match_export`.
The static website feature serves `index.html` as its index document.

## What it contains

- The React dashboard: Home, Fixtures, Match Hub with the replay, Teams, Players, Tech and Settings.
- The committed, deterministic data: `ui.json`, `insights.jsonl`, `claims.jsonl`, `timeline.json` and
  `matches/`. Every sentence in it comes from the templates (`agents/templates/`), not from a model.
- `healthz`, which answers `{"service":"static-replay"}`, so the app picks the replay source.

## What it deliberately does not contain

- No API: the FastAPI service (`service/app.py`) and its live SSE stream are not deployed here.
- No model calls: Azure OpenAI phrasing runs only from the repo (`--phraser azure`, Entra ID).
- No keys, connection strings or other secrets: the site is static files only.
