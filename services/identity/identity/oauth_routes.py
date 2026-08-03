"""OAuth 2.1 protocol endpoints exposed by TrackFlow Identity."""

from __future__ import annotations

import base64
import binascii
import logging
from html import escape
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .oauth import ACCESS_TOKEN_TYPE, TOKEN_EXCHANGE_GRANT, OAuthError, OAuthService
from .security import now_utc, oauth_jwks

router = APIRouter()
LOGGER = logging.getLogger(__name__)


def _service(request: Request) -> OAuthService:
    service = getattr(request.app.state, "oauth_service", None)
    if not isinstance(service, OAuthService):
        raise RuntimeError("OAuth service is not initialized.")
    return service


def _oauth_error(exc: OAuthError) -> JSONResponse:
    headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}
    if exc.error == "invalid_client":
        headers["WWW-Authenticate"] = 'Basic realm="oauth/token"'
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "error_description": exc.description},
        headers=headers,
    )


def _redirect(redirect_uri: str, *, state: str, **parameters: str) -> RedirectResponse:
    query = dict(parameters)
    if state:
        query["state"] = state
    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        f"{redirect_uri}{separator}{urlencode(query)}",
        status_code=303,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _authorization_error(
    service: OAuthService,
    values: dict[str, str],
    exc: OAuthError,
) -> JSONResponse | RedirectResponse:
    """Redirect protocol errors only after separately proving the callback is registered."""
    try:
        service.validate_redirect_uri(values["client_id"], values["redirect_uri"])
    except OAuthError:
        return _oauth_error(exc)
    return _redirect(
        values["redirect_uri"],
        state=values["state"],
        error=exc.error,
        error_description=exc.description,
    )


def _safe_client_id(value: str) -> str:
    """Keep attacker-controlled token-form fields out of OAuth audit records."""
    try:
        return str(UUID(value))
    except ValueError:
        return "unknown"


def _safe_grant(value: str) -> str:
    allowed = {"authorization_code", "client_credentials", TOKEN_EXCHANGE_GRANT}
    return value if value in allowed else "unknown"


def _authorization_fields(values: dict[str, str]) -> str:
    return "\n".join(
        f'<input type="hidden" name="{escape(key)}" value="{escape(value, quote=True)}">'
        for key, value in values.items()
    )


def _consent_page(values: dict[str, str], *, error: str = "", status_code: int = 200) -> HTMLResponse:
    scopes = [scope for scope in values["scope"].split(" ") if scope]
    scope_items = "".join(f"<li><code>{escape(scope)}</code></li>" for scope in scopes)
    error_html = f'<p role="alert">{escape(error)}</p>' if error else ""
    body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Authorize TrackFlow access</title>
    <style>
      body {{ font: 1rem/1.5 system-ui, sans-serif; margin: 0; background: #f5f7fa; color: #172033; }}
      main {{ max-width: 34rem; margin: 4rem auto; padding: 2rem; background: white; border-radius: .75rem; }}
      label {{ display: block; margin-top: 1rem; font-weight: 650; }}
      input {{ box-sizing: border-box; width: 100%; padding: .7rem; }}
      button {{ margin: 1.5rem .5rem 0 0; padding: .7rem 1rem; }}
      [role="alert"] {{ color: #a01919; }}
    </style>
  </head>
  <body>
    <main>
      <h1>Authorize TrackFlow access</h1>
      <p>Sign in and explicitly approve the requested permissions:</p>
      <ul>{scope_items}</ul>
      {error_html}
      <form method="post" action="/oauth/authorize">
        {_authorization_fields(values)}
        <label for="email">Email</label>
        <input id="email" name="email" type="email" autocomplete="username" required>
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required>
        <button type="submit" name="decision" value="approve">Approve</button>
        <button type="submit" name="decision" value="deny">Deny</button>
      </form>
    </main>
  </body>
</html>"""
    return HTMLResponse(
        body,
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _basic_credentials(request: Request) -> tuple[str | None, str | None]:
    authorization = request.headers.get("Authorization", "")
    scheme, _, encoded = authorization.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return None, None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None, None
    client_id, separator, client_secret = decoded.partition(":")
    if not separator:
        return None, None
    return client_id, client_secret


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata(request: Request) -> dict[str, object]:
    return _service(request).metadata()


@router.get("/oauth/jwks.json")
async def jwks(request: Request) -> dict[str, object]:
    return oauth_jwks(request.app.state.identity_settings)


@router.get("/oauth/authorize", response_class=HTMLResponse, response_model=None)
async def authorize_form(request: Request) -> HTMLResponse | JSONResponse | RedirectResponse:
    values = {
        key: request.query_params.get(key, "")
        for key in (
            "client_id",
            "redirect_uri",
            "response_type",
            "scope",
            "resource",
            "code_challenge",
            "code_challenge_method",
            "state",
        )
    }
    try:
        _service(request).validate_authorization_request(
            client_id=values["client_id"],
            redirect_uri=values["redirect_uri"],
            response_type=values["response_type"],
            scope=values["scope"],
            resource=values["resource"],
            code_challenge=values["code_challenge"],
            code_challenge_method=values["code_challenge_method"],
        )
    except OAuthError as exc:
        return _authorization_error(_service(request), values, exc)
    return _consent_page(values)


@router.post("/oauth/authorize", response_model=None)
async def authorize_submit(request: Request) -> HTMLResponse | JSONResponse | RedirectResponse:
    form = await request.form()
    values = {
        key: str(form.get(key, ""))
        for key in (
            "client_id",
            "redirect_uri",
            "response_type",
            "scope",
            "resource",
            "code_challenge",
            "code_challenge_method",
            "state",
        )
    }
    try:
        _service(request).validate_authorization_request(
            client_id=values["client_id"],
            redirect_uri=values["redirect_uri"],
            response_type=values["response_type"],
            scope=values["scope"],
            resource=values["resource"],
            code_challenge=values["code_challenge"],
            code_challenge_method=values["code_challenge_method"],
        )
    except OAuthError as exc:
        return _authorization_error(_service(request), values, exc)

    if str(form.get("decision", "")) != "approve":
        LOGGER.info(
            "oauth.audit client_id=%s subject=unknown grant=authorization_code outcome=denied timestamp=%s",
            _safe_client_id(values["client_id"]),
            now_utc().isoformat(),
        )
        return _redirect(
            values["redirect_uri"],
            state=values["state"],
            error="access_denied",
            error_description="The resource owner denied the request.",
        )

    try:
        code = _service(request).authorize(
            email=str(form.get("email", "")),
            password=str(form.get("password", "")),
            client_id=values["client_id"],
            redirect_uri=values["redirect_uri"],
            scope=values["scope"],
            resource=values["resource"],
            code_challenge=values["code_challenge"],
        )
    except OAuthError as exc:
        if exc.error == "access_denied":
            return _consent_page(values, error=exc.description, status_code=exc.status_code)
        return _oauth_error(exc)
    return _redirect(values["redirect_uri"], state=values["state"], code=code)


@router.post("/oauth/token")
async def token(request: Request) -> JSONResponse:
    form = await request.form()
    basic_id, basic_secret = _basic_credentials(request)
    client_id = basic_id or str(form.get("client_id", ""))
    client_secret = basic_secret if basic_id else (str(form["client_secret"]) if "client_secret" in form else None)
    grant_type = str(form.get("grant_type", ""))
    try:
        if grant_type == "authorization_code":
            issued = _service(request).exchange_authorization_code(
                client_id=client_id,
                client_secret=client_secret,
                code=str(form.get("code", "")),
                redirect_uri=str(form.get("redirect_uri", "")),
                code_verifier=str(form.get("code_verifier", "")),
            )
        elif grant_type == "client_credentials":
            issued = _service(request).client_credentials(
                client_id=client_id,
                client_secret=client_secret,
                scope=str(form.get("scope", "")),
                resource=str(form.get("resource", "")),
            )
        elif grant_type == TOKEN_EXCHANGE_GRANT:
            if str(form.get("subject_token_type", "")) != ACCESS_TOKEN_TYPE:
                raise OAuthError("invalid_request", "Only access-token subject tokens are supported.")
            issued = _service(request).token_exchange(
                client_id=client_id,
                client_secret=client_secret,
                subject_token=str(form.get("subject_token", "")),
                scope=str(form.get("scope", "")),
                resource=str(form.get("resource", "")),
            )
        else:
            raise OAuthError("unsupported_grant_type", "The requested grant type is not supported.")
    except OAuthError as exc:
        LOGGER.warning(
            "oauth.audit client_id=%s subject=unknown grant=%s outcome=%s timestamp=%s",
            _safe_client_id(client_id),
            _safe_grant(grant_type),
            exc.error,
            now_utc().isoformat(),
        )
        return _oauth_error(exc)

    return JSONResponse(
        {
            "access_token": issued.access_token,
            "token_type": "Bearer",
            "expires_in": issued.expires_in,
            "scope": issued.scope,
            "issued_token_type": ACCESS_TOKEN_TYPE,
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.post("/oauth/register", status_code=201)
async def register(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        record = _service(request).register_public_client(
            client_name=str(payload.get("client_name", "")),
            redirect_uris=[str(value) for value in payload.get("redirect_uris", [])],
            scopes=frozenset(str(payload.get("scope", "")).split()),
            resources=[str(value) for value in payload.get("resource", [])],
        )
    except (AttributeError, TypeError, ValueError):
        return _oauth_error(OAuthError("invalid_client_metadata", "The registration request is invalid."))
    except OAuthError as exc:
        return _oauth_error(exc)
    scopes = record.get("scopes")
    scope_text = " ".join(str(value) for value in scopes) if isinstance(scopes, list) else ""
    return JSONResponse(
        {
            "client_id": record["client_id"],
            "client_name": record["client_name"],
            "redirect_uris": record["redirect_uris"],
            "grant_types": record["grant_types"],
            "scope": scope_text,
            "resource": record["resources"],
            "token_endpoint_auth_method": record["token_endpoint_auth_method"],
        },
        status_code=201,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
