# Deploying Optix to Azure (manual; nothing here has been run)

These commands create resources and can cost money. The repo's automation never runs them; you do,
from your own shell, after reading them. Status: **built, not verified live** (see docs/AZURE.md).

## What gets created (infra/main.bicep)

- Log Analytics workspace + workspace-based Application Insights (telemetry from agents/telemetry.py).
- Container Apps environment + one container app (`optix-app`), external HTTPS ingress on port 8000,
  liveness/readiness on `/healthz`, scale 0-2, **system-assigned managed identity**.
- One role assignment: **Cognitive Services OpenAI User** for that identity, scoped to the one
  existing Azure OpenAI / Azure AI Foundry account you name. No API keys anywhere.

Prerequisites: an Azure subscription, an existing Azure OpenAI (or Foundry) account with a chat
deployment, a container registry you can push to, Azure CLI with Bicep, Docker.

## Commands

```bash
az login
az account set --subscription <subscription-id>
RG=optix-rg; LOC=<region>; ACR=<registry-name>

# 1. resource group and registry (skip what you already have)
az group create -n $RG -l $LOC
az acr create -g $RG -n $ACR --sku Basic

# 2. image
docker build -t $ACR.azurecr.io/optix:v1 .
az acr login -n $ACR
docker push $ACR.azurecr.io/optix:v1

# 3. lint, preview, deploy (fill infra/main.bicepparam first)
az bicep build --file infra/main.bicep
az deployment group what-if -g $RG --template-file infra/main.bicep --parameters infra/main.bicepparam
az deployment group create -g $RG --template-file infra/main.bicep --parameters infra/main.bicepparam

# 4. check it
curl -s https://<appUrl>/healthz
```

A private registry: create a user-assigned identity with AcrPull on the registry and pass
`registryServer` and `registryIdentityId` (the container app then pulls with that identity; still
no registry password).

## After deploying

- Open `https://<appUrl>/#/live`: the scoreboard chip should read **Live stream**.
- In Application Insights, Transaction search: spans `verifier.check`, `phraser.call`, `publish` appear
  when the pipeline runs with `APPLICATIONINSIGHTS_CONNECTION_STRING` set (the container has it).
- To phrase with the model inside the container:
  `az containerapp exec -g $RG -n optix-app --command "python -m agents.run_match --phraser azure --data data/showcase --season data/showcase --out /tmp/out/insights.jsonl"`.

## Remove everything

```bash
az group delete -n $RG
```
