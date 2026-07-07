# EngineRoom GA4 MCP Server

Google's official `analytics-mcp` (9 GA4 tools: run_report, run_realtime_report,
run_funnel_report, run_conversions_report, get_account_summaries,
get_property_details, get_custom_dimensions_and_metrics,
list_property_annotations, list_google_ads_links) served over streamable HTTP
with Google OAuth, suitable as a claude.ai **organization connector**.

Architecture: claude.ai → OAuth (users sign in with EngineRoom Google
accounts) → FastMCP proxy → analytics-mcp (stdio) → GA4 Data/Admin API using a
**service account** with Viewer access on the GA4 properties.

---

## 1. GCP setup (project: engineroom-184023)

### a. OAuth client (for user sign-in)
1. APIs & Services → Credentials → Create Credentials → **OAuth client ID** →
   type **Web application**.
2. Authorized redirect URI: `https://ga4-mcp.jsabino.cloud/auth/callback`
3. Note the client ID and secret.
4. OAuth consent screen → Audience: set to **Internal** so only
   engineroom.com.au accounts can authenticate. This is the actual access
   control for the connector.

### b. Service account (for GA4 data access)
1. IAM & Admin → Service Accounts → Create (e.g. `ga4-mcp-reader`).
2. Create a JSON key, download it.
3. Enable the **Google Analytics Data API** and **Google Analytics Admin API**
   in the project.
4. In each GA4 property (Admin → Property access management), add the service
   account email with **Viewer** role. Repeat for every client property the
   team should be able to query.

Base64-encode the key for the env var:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\path\to\sa-key.json"))
```

## 2. Coolify deployment

New Application → this repo/folder:

| Setting             | Value                          |
|---------------------|--------------------------------|
| Build Pack          | Dockerfile                     |
| Base Directory      | `/` (or `/ga4` in a monorepo)  |
| Dockerfile Location | `/Dockerfile`                  |
| Ports Exposes       | `8000`                         |
| Domain              | `https://ga4-mcp.jsabino.cloud`|

Environment variables:

```
BASE_URL=https://ga4-mcp.jsabino.cloud
GOOGLE_OAUTH_CLIENT_ID=<web client id>.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-...
GA4_SA_KEY_JSON_B64=<base64 of service account JSON>
```

Deploy, then verify:

```powershell
curl.exe -s https://ga4-mcp.jsabino.cloud/.well-known/oauth-protected-resource/mcp
# expect JSON metadata
curl.exe -s -o NUL -w "%{http_code}" -X POST https://ga4-mcp.jsabino.cloud/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d "{}"
# expect 401 (auth required) — NOT 404
```

## 3. Add as claude.ai organization connector

1. An **Owner/Primary Owner** of the EngineRoom workspace: Admin settings →
   Connectors → Add connector.
2. Server URL: `https://ga4-mcp.jsabino.cloud/mcp`  ← **no trailing slash**
   (FastMCP 3 redirects `/mcp/` → `/mcp`; note this is the opposite of the
   gads server).
3. Each team member clicks **Connect** on the connector and completes the
   Google sign-in. Internal consent screen restricts this to
   engineroom.com.au accounts.

Exact admin UI steps may shift — see https://support.claude.com (search
"custom connectors").

## Notes

- OAuth client registrations from claude.ai (dynamic client registration) are
  held by FastMCP's client storage; after a redeploy users may need to
  reconnect once. If that becomes annoying, pin `jwt_signing_key` and a
  persistent `client_storage` volume — ask before adding complexity.
- The stdio child process is spawned per session by the proxy; no keepalive
  hacks needed, but the same Cloudflare idle-stream behavior as the gads
  server applies to long SSE streams.
- To restrict *which* GA4 properties are visible, control it at the service
  account level (only grant Viewer on the properties you want exposed).
