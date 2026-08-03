# MCP OAuth Codespaces Runbook

Phase 3 exposes the TrackFlow tool boundary through Streamable HTTP at `/mcp`. Identity is the only
authorization server. This runbook uses placeholders deliberately: never paste client secrets,
authorization codes, access tokens, prompts, ticket descriptions, addresses, warehouse details, or
carrier rates into documentation, logs, screenshots, or traces.

The public Codespaces Playground exercise is the Phase 3 owner-review gate. It has not been executed
from the desktop workspace and must remain recorded as pending until the owner performs it.

## 1. Forward and configure the services

Forward the Identity port and MCP port as public only for the controlled review window. Record the
resulting HTTPS origins as:

```text
IDENTITY_PUBLIC=https://<identity-codespace-host>
MCP_PUBLIC=https://<mcp-codespace-host>/mcp
CENTRAL_RESOURCE=https://<central-api-codespace-host>
```

Configure Identity with `OAUTH_ISSUER_URL=$IDENTITY_PUBLIC`, `APP_ENVIRONMENT=codespaces`, and
`OAUTH_DYNAMIC_REGISTRATION_ENABLED=true`. Configure MCP with the same issuer, its internal Identity
URL for token exchange, `MCP_RESOURCE_URL=$MCP_PUBLIC`, and the Identity RS256 public key. Configure
Central API with separate internal transport URLs and the same public resource identifiers.

Restart the three services after changing URLs. Issuer and audience values are exact strings; a
forwarded URL change invalidates previously issued tokens and client resource allowlists.

## 2. Provision the two confidential service clients

Run these commands on the Identity host. Each secret is printed once; copy it directly into the
matching secret manager/environment field and do not save it in shell history or a file.

```bash
uv run --project services/identity python -m identity.cli create-oauth-client \
  --name central-agent \
  --grants urn:ietf:params:oauth:grant-type:token-exchange \
  --scopes mcp:connect,incidents:read \
  --resources "$MCP_PUBLIC" \
  --source-audiences trackflow-backoffice

uv run --project services/identity python -m identity.cli create-oauth-client \
  --name trackflow-mcp \
  --grants client_credentials,urn:ietf:params:oauth:grant-type:token-exchange \
  --scopes incidents:read,incidents:write,inventory:read \
  --resources "$CENTRAL_RESOURCE" \
  --source-audiences "$MCP_PUBLIC"
```

Set the first client as `AGENT_MCP_OAUTH_CLIENT_ID` / `AGENT_MCP_OAUTH_CLIENT_SECRET` in Central API.
Set the second as `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` in MCP.

## 3. Register and authorize the Playground

Register a public client with the Playground's exact redirect URI:

```bash
curl --fail-with-body -X POST "$IDENTITY_PUBLIC/oauth/register" \
  -H 'Content-Type: application/json' \
  --data '{
    "client_name":"Owner MCP Playground",
    "redirect_uris":["<exact-playground-callback>"],
    "scope":"mcp:connect incidents:read incidents:write inventory:read",
    "resource":["<exact-MCP_PUBLIC-value>"]
  }'
```

Configure the Playground for OAuth Authorization Code with S256 PKCE, the returned public client ID,
the exact MCP URL, and these Identity endpoints:

- authorization: `$IDENTITY_PUBLIC/oauth/authorize`
- token: `$IDENTITY_PUBLIC/oauth/token`
- metadata: `$IDENTITY_PUBLIC/.well-known/oauth-authorization-server`
- protected resource metadata: `$MCP_PUBLIC` rewritten as
  `$MCP_ORIGIN/.well-known/oauth-protected-resource/mcp`

Sign in with an active, permanent-password TrackFlow user. Inspect the requested scopes and choose
Approve. Verify the callback preserves `state`; do not copy the returned code or token into notes.

## 4. Owner-review acceptance checklist

In the Playground, capture pass/fail evidence without recording arguments or response content:

- discover exactly `ticket_check_status`, `ticket_create`, `ticket_update_status`, and
  `inventory_access`;
- invoke `ticket_check_status` against an approved test ticket;
- create an approved test ticket, then move it through an allowed status transition;
- run `inventory_access(action="list")` and `inventory_access(action="get", sku_id=<approved id>)`;
- run one controlled `inventory_access(action="delete", sku_id=<approved id>)` and verify
  `INVENTORY_READ_ONLY`, then confirm Central API received no request;
- remove `incidents:write` and verify ticket creation returns `INSUFFICIENT_SCOPE`;
- omit the bearer token and verify MCP discovery/invocation returns `401` with protected-resource
  metadata advertised.

After review, make the forwarded ports private again. Production domain, TLS, routing, secrets,
exposure, deployment, and rollback evidence require a separate owner approval.
