#!/usr/bin/env bash
# Re-runnable deployment of the Azure Pricing Dashboard to Azure Container Instances (ACI).
#
# Topology: a single multi-container group running
#   * caddy  — TLS termination (Let's Encrypt DNS-01 via Cloudflare), HTTP->HTTPS, reverse proxy
#   * app    — FastAPI + Uvicorn serving the API and static frontend on :8000
# Persistent state (JSON pricing snapshots + Caddy certs) lives on Azure Files.
#
# Run from WSL with the Azure CLI logged in (`az login`). Idempotent: safe to re-run for updates.
#
# Required vars come from deploy/.env (copy deploy/.env.example -> deploy/.env first).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy deploy/.env.example to deploy/.env and fill it in." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${RESOURCE_GROUP:?set RESOURCE_GROUP in .env}"
: "${LOCATION:?set LOCATION in .env}"
: "${ACR_NAME:?set ACR_NAME in .env}"
: "${STORAGE_ACCOUNT:?set STORAGE_ACCOUNT in .env}"
: "${CONTAINER_GROUP:?set CONTAINER_GROUP in .env}"
: "${DNS_LABEL:?set DNS_LABEL in .env}"
: "${APP_DOMAIN:?set APP_DOMAIN in .env}"
: "${ACME_EMAIL:?set ACME_EMAIL in .env}"
: "${CLOUDFLARE_API_TOKEN:?set CLOUDFLARE_API_TOKEN in .env}"

DEFAULT_CURRENCY="${DEFAULT_CURRENCY:-USD}"
CACHE_TTL_SECONDS="${CACHE_TTL_SECONDS:-3600}"
APP_SHARE="${APP_SHARE:-appdata}"
CADDY_SHARE="${CADDY_SHARE:-caddydata}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"

echo "==> Ensuring resource group $RESOURCE_GROUP ($LOCATION)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> Ensuring container registry $ACR_NAME"
az acr show --name "$ACR_NAME" --output none 2>/dev/null || \
  az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" \
    --sku Basic --admin-enabled true --output none

ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)"
APP_IMAGE="$ACR_LOGIN_SERVER/azure-pricing-app:$IMAGE_TAG"
CADDY_IMAGE="$ACR_LOGIN_SERVER/azure-pricing-caddy:$IMAGE_TAG"

echo "==> Building app image $APP_IMAGE"
az acr build --registry "$ACR_NAME" --image "azure-pricing-app:$IMAGE_TAG" \
  --file "$SCRIPT_DIR/Dockerfile" "$REPO_ROOT" --output none

echo "==> Building caddy image $CADDY_IMAGE"
az acr build --registry "$ACR_NAME" --image "azure-pricing-caddy:$IMAGE_TAG" \
  --file "$SCRIPT_DIR/Caddy.Dockerfile" "$REPO_ROOT" --output none

echo "==> Ensuring storage account $STORAGE_ACCOUNT + file shares"
az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null || \
  az storage account create --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" --sku Standard_LRS --output none

STORAGE_KEY="$(az storage account keys list --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" --query "[0].value" -o tsv)"

for share in "$APP_SHARE" "$CADDY_SHARE"; do
  az storage share create --name "$share" --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" --output none
done

ACR_USERNAME="$(az acr credential show --name "$ACR_NAME" --query username -o tsv)"
ACR_PASSWORD="$(az acr credential show --name "$ACR_NAME" --query 'passwords[0].value' -o tsv)"

echo "==> Rendering container group manifest"
RENDERED="$(mktemp)"
trap 'rm -f "$RENDERED"' EXIT

# Escape sed-special chars (/, &, |) in substituted values.
esc() { printf '%s' "$1" | sed -e 's/[\/&|]/\\&/g'; }

sed \
  -e "s|__LOCATION__|$(esc "$LOCATION")|g" \
  -e "s|__CONTAINER_GROUP__|$(esc "$CONTAINER_GROUP")|g" \
  -e "s|__DNS_LABEL__|$(esc "$DNS_LABEL")|g" \
  -e "s|__ACR_LOGIN_SERVER__|$(esc "$ACR_LOGIN_SERVER")|g" \
  -e "s|__ACR_USERNAME__|$(esc "$ACR_USERNAME")|g" \
  -e "s|__ACR_PASSWORD__|$(esc "$ACR_PASSWORD")|g" \
  -e "s|__APP_IMAGE__|$(esc "$APP_IMAGE")|g" \
  -e "s|__CADDY_IMAGE__|$(esc "$CADDY_IMAGE")|g" \
  -e "s|__STORAGE_ACCOUNT__|$(esc "$STORAGE_ACCOUNT")|g" \
  -e "s|__STORAGE_KEY__|$(esc "$STORAGE_KEY")|g" \
  -e "s|__APP_SHARE__|$(esc "$APP_SHARE")|g" \
  -e "s|__CADDY_SHARE__|$(esc "$CADDY_SHARE")|g" \
  -e "s|__DEFAULT_CURRENCY__|$(esc "$DEFAULT_CURRENCY")|g" \
  -e "s|__CACHE_TTL_SECONDS__|$(esc "$CACHE_TTL_SECONDS")|g" \
  -e "s|__APP_DOMAIN__|$(esc "$APP_DOMAIN")|g" \
  -e "s|__ACME_EMAIL__|$(esc "$ACME_EMAIL")|g" \
  -e "s|__CLOUDFLARE_API_TOKEN__|$(esc "$CLOUDFLARE_API_TOKEN")|g" \
  "$SCRIPT_DIR/container-group.yaml" > "$RENDERED"

echo "==> Deploying container group $CONTAINER_GROUP (replacing if it exists)"
az container delete --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_GROUP" --yes --output none 2>/dev/null || true
az container create --resource-group "$RESOURCE_GROUP" --file "$RENDERED" --output none

FQDN="$(az container show --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_GROUP" \
  --query ipAddress.fqdn -o tsv)"
PUBLIC_IP="$(az container show --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_GROUP" \
  --query ipAddress.ip -o tsv)"

cat <<EOF

==> Deployment complete.
    Container group FQDN : $FQDN
    Public IP            : $PUBLIC_IP

NEXT: point a Cloudflare DNS record for $APP_DOMAIN at $PUBLIC_IP
      (A record, DNS-only / grey cloud so Caddy can complete the ACME DNS-01 challenge),
      then browse https://$APP_DOMAIN
EOF
