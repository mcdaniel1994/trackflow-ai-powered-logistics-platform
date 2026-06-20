# `packages/trackflow_auth/`

Shared Python helpers for TrackFlow backend authentication.

This package is intentionally verify-only. The identity service signs RS256 access tokens with its private key; domain services import this package to validate access tokens with the public key, enforce active users, block temporary-password users from business routes, and check double-submit CSRF headers on state-changing cookie-authenticated requests.

It is a Python package, not an npm workspace package.
