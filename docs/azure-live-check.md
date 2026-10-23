# Azure live check

**Not run: no Azure configuration present** (2026-10-23T01:30:35+00:00).

- AZURE_OPENAI_ENDPOINT and/or AZURE_OPENAI_DEPLOYMENT not set
- Azure CLI (`az`) not installed, so no `az account show`

Nothing in this repo has been verified against a live Azure service. Everything Azure-related is "built, not verified live" (see docs/AZURE.md).

## How to run it

1. `az login` (Microsoft Entra ID; the phraser uses DefaultAzureCredential, no key needed).
2. Give your user the **Cognitive Services OpenAI User** role on the Azure OpenAI / Foundry resource.
3. Copy `.env.example` to `.env` and set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT`
   (optional: `AZURE_OPENAI_API_VERSION`, `APPLICATIONINSIGHTS_CONNECTION_STRING`).
4. `pip install -r requirements-azure.txt`
5. `python -m tools.azure_live_check` (at most 10 model calls), then
   `python -m pytest -m azure_live` for the live tests.
