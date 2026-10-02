"""Refreshable LinkedIn access token: a tiny on-disk store + OAuth refresh.

LinkedIn hands out short-lived member tokens (currently ~60 days), so the static
`LINKEDIN_ACCESS_TOKEN` in the environment goes stale within weeks and every
adapter call starts failing with HTTP 401. This module keeps a refresh token on
disk and mints a fresh access token from it on demand, so syndication keeps
working without hand-editing `.env`.

Everything is stdlib (`urllib`) - no SDK, no new dependency - and it is fully
backward compatible: when there is no token store and no OAuth client
credentials it simply returns the static `LINKEDIN_ACCESS_TOKEN`, exactly as the
adapter used to. It never raises when nothing is configured; it returns "".

One-time setup - do this once, after which the token refreshes itself:

    1. Print the authorization URL, open it, approve access, and copy the `code`
       parameter LinkedIn appends to your redirect URL:

           python -m src.syndication.linkedin_token

    2. Exchange that code for an access + refresh token (stored on disk):

           python -m src.syndication.linkedin_token <code>

Then `LinkedinSyndicator` reads the stored token through `access_token()`, which
refreshes it automatically as it nears expiry.

Scopes - this token is now requested for the Organization (Company Page):
`openid profile email w_organization_social r_organization_social` (see SCOPE).
The app must have the "Advertising API (Development Tier)" product so LinkedIn
grants those org scopes, and it must still be a scope-bearing request so LinkedIn
returns a refresh token. **A token minted against the old member-only scope
(`w_member_social`) predates the org scopes and cannot publish as the Page or read
Page analytics** - re-run the authorization step (delete/replace the stored token,
then repeat steps 1-2 above) so the authorize URL carries the org scopes and the
store holds a token that does. LinkedIn only returns the scopes actually granted
in the consent screen.

Env:
  LINKEDIN_CLIENT_ID       OAuth app client id (needed for any OAuth action)
  LINKEDIN_CLIENT_SECRET   OAuth app client secret (needed for any OAuth action)
  LINKEDIN_REDIRECT_URI    must match a redirect URL whitelisted on the app
  LINKEDIN_ACCESS_TOKEN    static token: used verbatim when OAuth is unavailable
  LINKEDIN_TOKEN_FILE      token store path (default: <repo>/data/linkedin_token.json)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv

# The setup CLI runs as `python -m src.syndication.linkedin_token` without the app,
# so load ".env" here (no override, so a real environment variable still wins).
load_dotenv()

TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
# Organization (Company Page) publishing + analytics. `w_organization_social`
# posts as the Page (the author URN is the organization URN - see
# linkedin.py:author_urn) and `r_organization_social` reads
# organizationalEntityShareStatistics (linkedin_metrics.py). Both need the app's
# "Advertising API / Development Tier" product and an org-scoped OAuth consent:
# re-run the authorize step after changing this so LinkedIn hands back a token
# carrying the new scopes (a token granted the old scopes will 403 on the Page).
SCOPE = "openid profile email w_member_social w_organization_social r_organization_social rw_organization_admin"

# Refresh a little *before* the token actually dies, so a call never races against
# expiry (the app may sit idle for hours between page renders and publishes).
EXPIRY_SKEW_SECONDS = 300

# <repo>/src/syndication/linkedin_token.py -> <repo> - the same resolution
# medium.py uses for MEDIUM_STATE_FILE, so both stores live side by side.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _store_path() -> str:
    """Absolute path of the token store. A relative value resolves from the repo root."""
    path = os.environ.get("LINKEDIN_TOKEN_FILE", "").strip() or os.path.join("data", "linkedin_token.json")
    if not os.path.isabs(path):
        path = os.path.join(_REPO_ROOT, path)
    return path


def _static_token() -> str:
    return os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()


def _client_credentials() -> tuple[str, str, str]:
    """(client_id, client_secret, redirect_uri) - any of which may be empty."""
    return (os.environ.get("LINKEDIN_CLIENT_ID", "").strip(),
            os.environ.get("LINKEDIN_CLIENT_SECRET", "").strip(),
            os.environ.get("LINKEDIN_REDIRECT_URI", "").strip())


def _load_store() -> dict:
    """Read the token store. A missing or corrupt file simply means "no token"."""
    try:
        with open(_store_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_store(data: dict) -> None:
    """Write the store atomically (temp file + replace) so a crash cannot truncate it."""
    path = _store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def _expires_at(payload: dict, now: float) -> float:
    """Absolute expiry from a token response (`expires_in` is a lifetime in seconds)."""
    try:
        seconds = float(payload.get("expires_in"))
    except (TypeError, ValueError):
        # No lifetime advertised: fall back to LinkedIn's documented member default.
        seconds = 60.0 * 60 * 24 * 60
    return now + seconds


def _is_expiring(store: dict) -> bool:
    """True when the stored token is inside the refresh window.

    An unknown `expires_at` is treated as still valid: the store is always written
    with one, so its absence means a hand-crafted file the author wants honoured.
    """
    expires_at = store.get("expires_at")
    if expires_at is None:
        return False
    try:
        remaining = float(expires_at) - time.time()
    except (TypeError, ValueError):
        return False
    return remaining <= EXPIRY_SKEW_SECONDS


def _post(params: dict) -> dict:
    """POST form-encoded params to the token endpoint; return the decoded JSON body."""
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8")) or {}


def _persist(payload: dict, scope: str | None = None) -> str:
    """Store a token response and return its access token ("" when none came back).

    A refresh rotates the refresh token, so the store is rewritten wholesale from
    whatever the response carried; when a response omits the refresh token the
    previous one is kept rather than dropped.
    """
    access = (payload.get("access_token") or "").strip()
    if not access:
        return ""
    current = _load_store()
    _save_store({
        "access_token": access,
        "refresh_token": (payload.get("refresh_token") or current.get("refresh_token") or "").strip(),
        "expires_at": _expires_at(payload, time.time()),
        "scope": (payload.get("scope") or scope or current.get("scope") or SCOPE),
    })
    return access


def access_token() -> str:
    """A usable LinkedIn access token, or "" when nothing at all is configured.

    Order:
      1. a stored token that is still comfortably valid (outside the 5-minute window);
      2. otherwise a refresh grant - when a refresh token *and* client id/secret exist;
      3. otherwise the static LINKEDIN_ACCESS_TOKEN, then any stale stored token.

    A failed refresh never raises: it falls through to (3), and `check()` is left
    to surface the real problem.
    """
    store = _load_store()
    stored = (store.get("access_token") or "").strip()
    if stored and not _is_expiring(store):
        return stored

    client_id, client_secret, _ = _client_credentials()
    refresh = (store.get("refresh_token") or "").strip()
    if refresh and client_id and client_secret:
        try:
            refreshed = _post({
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            })
        except Exception:
            refreshed = None
        if isinstance(refreshed, dict):
            token = _persist(refreshed)
            if token:
                return token

    # (c) Nothing refreshable: use the static token; then a stale stored one we
    # cannot renew (no worse than the static token, and it is what the author put
    # there). Finally "" - never raise.
    return _static_token() or stored


def has_credentials() -> bool:
    """True when a token is available: a stored one (fresh or refreshable), or the static env token.

    Cheap and offline, so the adapter can call it on every page render.
    """
    store = _load_store()
    if (store.get("access_token") or "").strip():
        return True
    refresh = (store.get("refresh_token") or "").strip()
    client_id, client_secret, _ = _client_credentials()
    if refresh and client_id and client_secret:
        return True
    return bool(_static_token())


def authorize_url(state: str | None = None) -> str:
    """LinkedIn's authorization URL for the one-time consent step."""
    client_id, _, redirect_uri = _client_credentials()
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPE,
    }
    if state:
        params["state"] = state
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(code: str) -> str:
    """Auth-code grant: persist access + refresh + expiry and return the access token.

    Raises ValueError when the OAuth client is not configured or LinkedIn returns
    no access token - this is the interactive setup step, so failing loudly beats a
    silent no-op.
    """
    client_id, client_secret, redirect_uri = _client_credentials()
    if not (client_id and client_secret and redirect_uri):
        raise ValueError("Set LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET and "
                         "LINKEDIN_REDIRECT_URI before exchanging a code.")
    payload = _post({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    })
    token = _persist(payload)
    if not token:
        raise ValueError("LinkedIn did not return an access token: %s" % (payload,))
    return token


def main(argv: list[str] | None = None) -> int:
    """CLI: no args prints the authorize URL; a code argument exchanges and stores it."""
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] not in ("-h", "--help"):
        try:
            exchange_code(args[0].strip())
        except Exception as e:
            print("Token exchange failed: %s" % e, file=sys.stderr)
            return 1
        print("Stored a fresh LinkedIn token in %s" % _store_path())
        return 0

    _, _, redirect_uri = _client_credentials()
    print("Open the URL below, approve access, then copy the `code` parameter")
    print("LinkedIn appends to your redirect URL (%s)." % (redirect_uri or "<LINKEDIN_REDIRECT_URI not set>"))
    print()
    print(authorize_url())
    print()
    print("Then run:  python -m src.syndication.linkedin_token <code>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
