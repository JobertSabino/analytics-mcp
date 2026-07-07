"""EngineRoom GA4 MCP server.

Wraps Google's official `analytics-mcp` (stdio) in a FastMCP streamable-HTTP
proxy, protected by Google OAuth so it can be added as a claude.ai
organization connector. Team members authenticate with their EngineRoom
Google accounts; the server itself reads GA4 via a service account (ADC).
"""

import base64
import os
import sys

from fastmcp.server import create_proxy
from fastmcp.server.auth.providers.google import GoogleProvider

# --- Required environment variables -----------------------------------------
BASE_URL = os.environ["BASE_URL"]  # e.g. https://ga4-mcp.jsabino.cloud
OAUTH_CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
OAUTH_CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]

# --- GA4 data credentials (service account, used by analytics-mcp via ADC) --
# Provide the service-account key as base64 in GA4_SA_KEY_JSON_B64 so it can
# live in a Coolify env var instead of the image.
sa_b64 = os.environ.get("GA4_SA_KEY_JSON_B64")
if sa_b64:
    sa_path = "/app/sa.json"
    with open(sa_path, "wb") as f:
        f.write(base64.b64decode(sa_b64))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
elif not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    print(
        "WARNING: no GA4_SA_KEY_JSON_B64 or GOOGLE_APPLICATION_CREDENTIALS set; "
        "GA4 tool calls will fail.",
        file=sys.stderr,
    )

# --- OAuth for connecting users (claude.ai org connector) -------------------
auth = GoogleProvider(
    client_id=OAUTH_CLIENT_ID,
    client_secret=OAUTH_CLIENT_SECRET,
    base_url=BASE_URL,
    redirect_path="/auth/callback",
    required_scopes=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
    # Hint Google's account picker to the workspace domain. Enforcement comes
    # from setting the OAuth consent screen to "Internal" in GCP.
    extra_authorize_params={"hd": "engineroom.com.au"},
)

# --- Proxy the official stdio analytics-mcp over streamable HTTP ------------
mcp = create_proxy(
    {"mcpServers": {"ga4": {"command": "analytics-mcp", "args": []}}},
    name="EngineRoom GA4 Analytics",
    auth=auth,
)

if __name__ == "__main__":
    public_host = BASE_URL.split("://", 1)[-1].rstrip("/")
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        # FastMCP's DNS-rebinding guard only trusts localhost by default;
        # allow the public hostname (and its origin) or every proxied
        # request is rejected with 421 Misdirected Request.
        allowed_hosts=[public_host],
        allowed_origins=[BASE_URL.rstrip("/")],
    )
