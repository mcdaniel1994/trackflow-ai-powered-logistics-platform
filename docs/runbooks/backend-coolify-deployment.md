# Backend and Back Office Coolify Deployment

## Status

Prepared, not production-verified. Every production migration, seed, DNS,
firewall, and deployment action requires explicit owner approval.

## Prerequisites

- Confirm the owner inputs in `docs/planning/deployment-dockerization.md`.
- Prove both restore drills before creating the first production account.
- Store secrets only in Coolify. Identity receives the private and public JWT
  keys; Central API receives only the public key.
- Use the exact Supabase direct or Session-mode connection strings from its
  dashboard with `sslmode=require`; never use transaction mode `:6543`.

## Order

1. Create least-privilege database roles using the Supabase runbook.
2. Back up, migrate a disposable target, and prove restore.
3. Run `central-api-migrate` as an explicit setup-profile one-off.
4. Deploy Identity with its persistent `/data` volume; verify `/health`.
5. Run `python -m identity.cli create-admin` in the Identity container and
   securely record its stable UUID.
6. Run `seed-inventory` with that UUID, then `seed-suppliers`. Never run
   `seed-incidents` in production.
7. Deploy Central API and verify `/health` reports database `ok`.
8. Deploy Back Office and route only port 3000 through Traefik.
9. Verify HTTPS login, `Secure; HttpOnly` cookies, CSRF writes, reset email,
   inventory, incidents, suppliers, and all health endpoints.
10. Confirm internet requests cannot reach Identity or Central API.

In Coolify, run setup services explicitly from `compose.coolify.yaml`; a normal
stack deploy must not enable the `setup` profile.

## Rollback

Roll the Compose stack back to retained images. Never automatically downgrade
the schema; use expand/contract and forward fixes. A data restore is a
last-resort, approval-gated operation. Restoring Identity also requires
`revoke-sessions` and JWT key rotation per the Identity runbook.
