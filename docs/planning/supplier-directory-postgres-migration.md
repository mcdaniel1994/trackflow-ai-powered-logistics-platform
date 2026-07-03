# Supplier Directory PostgreSQL Migration

## Status

Implemented locally; production cutover and retirement remain approval-gated.

## Boundary waiver

The Supplier Directory is intentionally folded into Central API as a
PostgreSQL-backed `suppliers` domain. This waives the default independent
service boundary in `services/README.md` to reduce the production container
count while retaining Identity as a separate security boundary.

## Preserved contract

- Existing `/suppliers` paths, filters, ordering, validation, and error status
  codes remain stable.
- List and detail responses expose `has_contact_email`, never the raw address.
- Raw contact email remains available only through the explicit authenticated
  `/suppliers/{id}/contact` reveal endpoint.
- The importer preserves UUIDs, `rate_updated_at`, nullable fields, categories,
  rates, currency, status, service zones, notes, and contact email.

## Cutover

1. Announce a supplier write freeze.
2. Copy the original TinyDB file to an isolated snapshot; never import the live
   file while it is being written.
3. Run migrations and the importer against staging, then compare every field,
   count, list order, and `has_contact_email`.
4. Repeat against production only after explicit approval and a database
   backup.
5. Point Back Office at Central API and observe through the agreed rollback
   window.
6. Retire `services/supplier-directory/` only after the owner closes that
   window. Until then, the original TinyDB file remains untouched.
