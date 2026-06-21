<#
  deploy-app-only.ps1 — App-only Path A deployment (no Caddy / no TLS).

  Builds the FastAPI app image in ACR and deploys a single-container group with a
  public DNS label exposing port 443 (TLS, self-signed) so Cloudflare's proxy can
  connect to the origin over HTTPS in "Full" SSL mode.
  Prints the FQDN + public IP so you can point your own DNS at it manually.

  Uses the Windows Azure CLI (avoids the WSL `az` token-refresh hang).

  Usage (from a PowerShell prompt, with `az login` already done):
      cd deploy
      ./deploy-app-only.ps1

  Reads configuration from deploy/.env (CLOUDFLARE_API_TOKEN / ACME_EMAIL not required).
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

$RESOURCE_GROUP   = Req 'RESOURCE_GROUP'
$LOCATION         = Req 'LOCATION'
$ACR_NAME         = Req 'ACR_NAME'
$STORAGE_ACCOUNT  = Req 'STORAGE_ACCOUNT'
$CONTAINER_GROUP  = Req 'CONTAINER_GROUP'
$DNS_LABEL        = Req 'DNS_LABEL'

$DEFAULT_CURRENCY  = if ($cfg['DEFAULT_CURRENCY'])  { $cfg['DEFAULT_CURRENCY'] }  else { 'USD' }
$CACHE_TTL_SECONDS = if ($cfg['CACHE_TTL_SECONDS']) { $cfg['CACHE_TTL_SECONDS'] } else { '3600' }
$APP_SHARE         = if ($cfg['APP_SHARE'])         { $cfg['APP_SHARE'] }         else { 'appdata' }
$IMAGE_TAG         = if ($cfg['IMAGE_TAG'])         { $cfg['IMAGE_TAG'] }         else { Get-Date -Format 'yyyyMMddHHmmss' }

function Invoke-Az {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & az @Args
    if ($LASTEXITCODE -ne 0) { throw "az $($Args -join ' ') failed (exit $LASTEXITCODE)" }
}

# Runs an `az ... show` style check without letting its stderr/exit terminate the script.
function Test-AzExists {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & az @Args *> $null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return ($code -eq 0)
}

Write-Host "==> Ensuring resource group $RESOURCE_GROUP ($LOCATION)"
Invoke-Az group create --name $RESOURCE_GROUP --location $LOCATION --output none

Write-Host "==> Ensuring container registry $ACR_NAME"
if (-not (Test-AzExists acr show --name $ACR_NAME --output none)) {
    Invoke-Az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME `
        --sku Basic --admin-enabled true --output none
}

$ACR_LOGIN_SERVER = (& az acr show --name $ACR_NAME --query loginServer -o tsv).Trim()
$APP_IMAGE = "$ACR_LOGIN_SERVER/azure-pricing-app:$IMAGE_TAG"

Write-Host "==> Building app image $APP_IMAGE"
if (Test-AzExists acr repository show --name $ACR_NAME --image "azure-pricing-app:$IMAGE_TAG" --output none) {
    Write-Host "    Image tag already exists in registry; skipping build."
} else {
    Invoke-Az acr build --registry $ACR_NAME --image "azure-pricing-app:$IMAGE_TAG" `
        --file (Join-Path $ScriptDir 'Dockerfile') $RepoRoot --output none
}

$ACR_USERNAME = (& az acr credential show --name $ACR_NAME --query username -o tsv).Trim()
$ACR_PASSWORD = (& az acr credential show --name $ACR_NAME --query 'passwords[0].value' -o tsv).Trim()

Write-Host "==> Rendering container group manifest"
$template = Get-Content (Join-Path $ScriptDir 'container-group-app.yaml') -Raw
$map = @{
    '__LOCATION__'           = $LOCATION
    '__CONTAINER_GROUP__'    = $CONTAINER_GROUP
    '__DNS_LABEL__'          = $DNS_LABEL
    '__ACR_LOGIN_SERVER__'   = $ACR_LOGIN_SERVER
    '__ACR_USERNAME__'       = $ACR_USERNAME
    '__ACR_PASSWORD__'       = $ACR_PASSWORD
    '__APP_IMAGE__'          = $APP_IMAGE
    '__DEFAULT_CURRENCY__'   = $DEFAULT_CURRENCY
    '__CACHE_TTL_SECONDS__'  = $CACHE_TTL_SECONDS
}
foreach ($k in $map.Keys) { $template = $template.Replace($k, $map[$k]) }

$rendered = Join-Path ([System.IO.Path]::GetTempPath()) "container-group-app-$IMAGE_TAG.yaml"
[System.IO.File]::WriteAllText($rendered, $template, (New-Object System.Text.UTF8Encoding $false))
try {
    Write-Host "==> Deploying container group $CONTAINER_GROUP (replacing if it exists)"
    [void](Test-AzExists container delete --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP --yes --output none)
    Invoke-Az container create --resource-group $RESOURCE_GROUP --file $rendered --output none

    $FQDN = (& az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP `
        --query ipAddress.fqdn -o tsv).Trim()
    $PUBLIC_IP = (& az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP `
        --query ipAddress.ip -o tsv).Trim()

    Write-Host ""
    Write-Host "==> Deployment complete."
    Write-Host "    Container group FQDN : $FQDN"
    Write-Host "    Public IP            : $PUBLIC_IP"
    Write-Host "    App URL              : https://$FQDN/  (self-signed cert)"
    Write-Host ""
    Write-Host "NEXT: in Cloudflare, add a proxied (orange-cloud) CNAME -> $FQDN"
    Write-Host "      (or A record -> $PUBLIC_IP). Set SSL/TLS mode to 'Full' so Cloudflare"
    Write-Host "      connects to this origin over HTTPS on port 443. Use 'Full' (not"
    Write-Host "      Full-strict) since the origin cert is self-signed."
}
finally {
    Remove-Item -Path $rendered -ErrorAction SilentlyContinue
}
