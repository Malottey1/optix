using './main.bicep'

// Fill these in for your subscription; no secrets belong here.
param namePrefix = 'optix'
param image = '<registry>.azurecr.io/optix:<tag>'
param openAiAccountName = '<existing-azure-openai-account>'
param openAiDeployment = '<chat-deployment-name>'
