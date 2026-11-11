#!/usr/bin/env bash
# Hardens the App Service with Azure CLI settings. Run it yourself, in your own
# subscription, after reading each command. It changes live settings.
#
# Usage:
#   az login
#   ./scripts/harden-webapp.sh <resource-group> [app-name]
#
# After running, push a commit (or re-run the workflow) and confirm the deployment
# and the /health smoke test still pass.

set -euo pipefail

RG="${1:?Usage: $0 <resource-group> [app-name]}"
APP="${2:-ttscott-webapp}"

echo "==> Require HTTPS (redirect plain HTTP)"
az webapp update --resource-group "$RG" --name "$APP" --https-only true

echo "==> TLS 1.2 minimum, HTTP/2 on, FTP/FTPS off"
az webapp config set --resource-group "$RG" --name "$APP" \
  --min-tls-version 1.2 \
  --http20-enabled true \
  --ftps-state Disabled

echo "==> Let App Service probe /health and replace unhealthy instances"
az webapp config set --resource-group "$RG" --name "$APP" \
  --generic-configurations '{"healthCheckPath": "/health"}'

echo "==> Turn on a system-assigned managed identity (use it instead of stored secrets)"
az webapp identity assign --resource-group "$RG" --name "$APP"

echo "==> Turn off basic-auth publishing (deployments use Entra ID / OIDC instead)"
for policy in ftp scm; do
  az resource update \
    --resource-group "$RG" \
    --name "$policy" \
    --namespace Microsoft.Web \
    --resource-type basicPublishingCredentialsPolicies \
    --parent "sites/$APP" \
    --set properties.allow=false
done

echo "==> Send App Service logs to Log Analytics (set WORKSPACE_ID to enable)"
if [[ -n "${WORKSPACE_ID:-}" ]]; then
  APP_ID="$(az webapp show --resource-group "$RG" --name "$APP" --query id -o tsv)"
  az monitor diagnostic-settings create \
    --name "appservice-to-loganalytics" \
    --resource "$APP_ID" \
    --workspace "$WORKSPACE_ID" \
    --logs '[{"category":"AppServiceHTTPLogs","enabled":true},{"category":"AppServiceConsoleLogs","enabled":true},{"category":"AppServiceAppLogs","enabled":true}]'
else
  echo "    skipped (export WORKSPACE_ID=<full Log Analytics workspace resource ID> to enable)"
fi

echo "Done. Verify:  az webapp show -g $RG -n $APP --query '{https:httpsOnly, identity:identity.type}'"
