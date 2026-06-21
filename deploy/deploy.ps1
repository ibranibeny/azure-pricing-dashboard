<#
  deploy.ps1 — PowerShell port of deploy.sh for the Azure Pricing Dashboard.

  Runs the full Path B deployment (multi-container ACI: caddy + app, Azure Files,
  Let's Encrypt TLS via Cloudflare DNS-01) using the *Windows* Azure CLI, which
  avoids the token-refresh hang seen with the WSL `az`.

  Usage (from a PowerShell prompt, with `az login` already done):
      cd deploy
      ./deploy.ps1

  Reads configuration from deploy/.env (same file deploy.sh uses).
#>

$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$RepoRoot  = Split-Path -Parent $ScriptDir
$EnvFile   = Join-Path $ScriptDir '.env'

if (-not (Test-Path $EnvFile)) {
    throw "ERROR: $EnvFile not found. Copy deploy/.env.example to deploy/.env and fill it in."
}

# --- Load .env (KEY=VALUE lines, ignore blanks/comments) -------------------
$cfg = @{}
foreach ($line in Get-Content $EnvFile) {
    $t = $line.Trim()
    if ($t -eq '' -or $t.StartsWith('#')) { continue }
    $idx = $t.IndexOf('=')
    if ($idx -lt 1) { continue }
    $key = $t.Substring(0, $idx).Trim()
    $val = $t.Substring($idx + 1).Trim()
    if (($val.StartsWith('"') -and $val.EndsWith('"')) -or
        ($val.StartsWith("'") -and $val.EndsWith("'"))) {
        $val = $val.Substring(1, $val.Length - 2)
    }
    $cfg[$key] = $val
}

function Req([string]$name) {
    if (-not $cfg.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($cfg[$name])) {
        throw "set $name in .env"
    }
    return $cfg[$name]
}

$RESOURCE_GROUP       = Req 'RESOURCE_GROUP'
$LOCATION             = Req 'LOCATION'
$ACR_NAME             = Req 'ACR_NAME'
$STORAGE_ACCOUNT      = Req 'STORAGE_ACCOUNT'
$CONTAINER_GROUP      = Req 'CONTAINER_GROUP'
$DNS_LABEL            = Req 'DNS_LABEL'
$APP_DOMAIN           = Req 'APP_DOMAIN'
$ACME_EMAIL           = Req 'ACME_EMAIL'
$CLOUDFLARE_API_TOKEN = Req 'CLOUDFLARE_API_TOKEN'

if ($CLOUDFLARE_API_TOKEN -eq 'cf-replace-me') {
    throw "CLOUDFLARE_API_TOKEN is still the placeholder 'cf-replace-me'. Paste your real Cloudflare token into deploy/.env first."
}

$DEFAULT_CURRENCY   = if ($cfg['DEFAULT_CURRENCY'])   { $cfg['DEFAULT_CURRENCY'] }   else { 'USD' }
$CACHE_TTL_SECONDS  = if ($cfg['CACHE_TTL_SECONDS'])  { $cfg['CACHE_TTL_SECONDS'] }  else { '3600' }
$APP_SHARE          = if ($cfg['APP_SHARE'])          { $cfg['APP_SHARE'] }          else { 'appdata' }
$CADDY_SHARE        = if ($cfg['CADDY_SHARE'])        { $cfg['CADDY_SHARE'] }        else { 'caddydata' }
$IMAGE_TAG          = if ($cfg['IMAGE_TAG'])          { $cfg['IMAGE_TAG'] }          else { Get-Date -Format 'yyyyMMddHHmmss' }

function Invoke-Az {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & az @Args
    if ($LASTEXITCODE -ne 0) { throw "az $($Args -join ' ') failed (exit $LASTEXITCODE)" }
}

Write-Host "==> Ensuring resource group $RESOURCE_GROUP ($LOCATION)"
Invoke-Az group create --name $RESOURCE_GROUP --location $LOCATION --output none

Write-Host "==> Ensuring container registry $ACR_NAME"
& az acr show --name $ACR_NAME --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    Invoke-Az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME `
        --sku Basic --admin-enabled true --output none
}

$ACR_LOGIN_SERVER = (& az acr show --name $ACR_NAME --query loginServer -o tsv).Trim()
$APP_IMAGE   = "$ACR_LOGIN_SERVER/azure-pricing-app:$IMAGE_TAG"
$CADDY_IMAGE = "$ACR_LOGIN_SERVER/azure-pricing-caddy:$IMAGE_TAG"

Write-Host "==> Building app image $APP_IMAGE"
Invoke-Az acr build --registry $ACR_NAME --image "azure-pricing-app:$IMAGE_TAG" `
    --file (Join-Path $ScriptDir 'Dockerfile') $RepoRoot --output none

Write-Host "==> Building caddy image $CADDY_IMAGE"
Invoke-Az acr build --registry $ACR_NAME --image "azure-pricing-caddy:$IMAGE_TAG" `
    --file (Join-Path $ScriptDir 'Caddy.Dockerfile') $RepoRoot --output none

Write-Host "==> Ensuring storage account $STORAGE_ACCOUNT + file shares"
& az storage account show --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    Invoke-Az storage account create --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP `
        --location $LOCATION --sku Standard_LRS --output none
}

$STORAGE_KEY = (& az storage account keys list --account-name $STORAGE_ACCOUNT `
    --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv).Trim()

foreach ($share in @($APP_SHARE, $CADDY_SHARE)) {
    Invoke-Az storage share create --name $share --account-name $STORAGE_ACCOUNT `
        --account-key $STORAGE_KEY --output none
}

$ACR_USERNAME = (& az acr credential show --name $ACR_NAME --query username -o tsv).Trim()
$ACR_PASSWORD = (& az acr credential show --name $ACR_NAME --query 'passwords[0].value' -o tsv).Trim()

Write-Host "==> Rendering container group manifest"
$template = Get-Content (Join-Path $ScriptDir 'container-group.yaml') -Raw
$map = @{
    '__LOCATION__'             = $LOCATION
    '__CONTAINER_GROUP__'      = $CONTAINER_GROUP
    '__DNS_LABEL__'            = $DNS_LABEL
    '__ACR_LOGIN_SERVER__'     = $ACR_LOGIN_SERVER
    '__ACR_USERNAME__'         = $ACR_USERNAME
    '__ACR_PASSWORD__'         = $ACR_PASSWORD
    '__APP_IMAGE__'            = $APP_IMAGE
    '__CADDY_IMAGE__'          = $CADDY_IMAGE
    '__STORAGE_ACCOUNT__'      = $STORAGE_ACCOUNT
    '__STORAGE_KEY__'          = $STORAGE_KEY
    '__APP_SHARE__'            = $APP_SHARE
    '__CADDY_SHARE__'          = $CADDY_SHARE
    '__DEFAULT_CURRENCY__'     = $DEFAULT_CURRENCY
    '__CACHE_TTL_SECONDS__'    = $CACHE_TTL_SECONDS
    '__APP_DOMAIN__'           = $APP_DOMAIN
    '__ACME_EMAIL__'           = $ACME_EMAIL
    '__CLOUDFLARE_API_TOKEN__' = $CLOUDFLARE_API_TOKEN
}
foreach ($k in $map.Keys) { $template = $template.Replace($k, $map[$k]) }

$rendered = Join-Path ([System.IO.Path]::GetTempPath()) "container-group-$IMAGE_TAG.yaml"
Set-Content -Path $rendered -Value $template -Encoding utf8
try {
    Write-Host "==> Deploying container group $CONTAINER_GROUP (replacing if it exists)"
    & az container delete --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP --yes --output none 2>$null
    Invoke-Az container create --resource-group $RESOURCE_GROUP --file $rendered --output none

    $FQDN = (& az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP `
        --query ipAddress.fqdn -o tsv).Trim()
    $PUBLIC_IP = (& az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP `
        --query ipAddress.ip -o tsv).Trim()

    Write-Host ""
    Write-Host "==> Deployment complete."
    Write-Host "    Container group FQDN : $FQDN"
    Write-Host "    Public IP            : $PUBLIC_IP"
    Write-Host ""
    Write-Host "NEXT: point a Cloudflare DNS record for $APP_DOMAIN at $PUBLIC_IP"
    Write-Host "      (A record, DNS-only / grey cloud so Caddy can complete the ACME DNS-01 challenge),"
    Write-Host "      then browse https://$APP_DOMAIN"
}
finally {
    Remove-Item -Path $rendered -ErrorAction SilentlyContinue
}
