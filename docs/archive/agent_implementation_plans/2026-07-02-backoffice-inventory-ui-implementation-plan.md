# Backoffice Inventory Management UI — Implementation Plan

## Summary

Create four authenticated inventory views under `/backoffice/inventory/...`, consuming Central API exclusively through the same-origin BFF. Preserve Engagement 2, the delivered Engagement 5 backend, `packages/shared`, and `uis/website`.

## Implementation

- Add an allowlisted `/api/inventory/[[...path]]` BFF proxy with cookie authentication, CSRF forwarding, timeouts, and safe errors.
- Add `CENTRAL_API_URL` as server-only configuration.
- Create a typed centralized inventory client; components must not call `fetch` directly.
- Add navigation while preserving the existing Inventory + Carriers dashboard.
- Build:
  - `/backoffice/inventory/products`: paginated products, stock indicators, inbound/outbound links.
  - `/backoffice/inventory/orders/inbound`: product selector, receipt reference, quantity, visible success/errors.
  - `/backoffice/inventory/orders/outbound`: reactive stock lookup, dispatch/loss fields, overstock warning, inline API `400`.
  - `/backoffice/inventory/orders`: paginated read-only movement history with product, quantity, type, warehouse, date, and `user_uuid`.
- Use stock thresholds: `0` out, `1–10` low, `11+` healthy.
- Derive SKU ID and warehouse from product selection; never submit `current_stock` or `user_uuid`.
- Update the Backoffice README and `.env.example`.
- Add brief teaching comments in meaningful changed source files.
- Do not alter engagement tracking or classification.

## Verification

- Test BFF allowlisting, cookies, CSRF, query forwarding, `401`, `503`, and `504`.
- Test client error parsing and pagination.
- Test product indicators, form validation/reset, reactive stock, tracking rules, insufficient-stock errors, and history rendering.
- Verify unauthenticated redirects for all four routes.
- Run Vitest, Playwright, type-check, lint, build, and `git diff --check`.
- Browser-test authenticated inbound/outbound flows against locally running Identity, PostgreSQL, and Central API.

## Assumptions

- The attachment’s literal `/backoffice/inventory/...` routes are authoritative.
- Authentication remains HttpOnly-cookie based; no browser token storage.
- Raw `user_uuid` is displayed because no identity-name lookup exists.
- Product creation is out of scope.
- Central API uses an available local port configured through `CENTRAL_API_URL`.
- Existing standards commit `1c1122d` remains untouched.
