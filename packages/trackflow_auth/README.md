# `packages/trackflow_auth/`

Shared Python helpers for TrackFlow backend authentication and safe FastAPI validation errors.

This package is intentionally small and security-boundary focused. The identity service signs RS256 access tokens with its private key; domain services import this package to validate access tokens with the public key, enforce active users, block temporary-password users from business routes, and check double-submit CSRF headers on state-changing cookie-authenticated requests.

It also exposes `safe_request_validation_exception_handler`, a shared `RequestValidationError` handler that preserves FastAPI's field-level 422 shape while stripping submitted `input`, `ctx`, tokens, passwords, emails, and raw exception detail from API responses.

Engagement 8 adds `authenticate_scoped_bearer` for OAuth resource endpoints. It accepts bearer
tokens only, verifies the URL issuer, exact audience, RS256 signature and lifetime, and enforces an
explicit required-scope set. Existing Back Office cookie/bearer verification remains unchanged;
each service decides which routes may additionally accept scoped OAuth principals.

It is a Python package, not an npm workspace package.

## Tests

```bash
COVERAGE_FILE=/tmp/trackflow-auth.coverage uv run --with pytest --with pytest-cov pytest --cov=trackflow_auth --cov-report=term-missing
```
