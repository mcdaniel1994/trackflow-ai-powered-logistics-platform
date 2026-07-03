# Identity TinyDB Backup and Restore

## Backup

1. Quiesce the single Identity writer or snapshot its volume atomically.
2. Copy the `identity-data` volume's `identity.json` to encrypted off-site storage.
3. Validate the copy as JSON without printing user/session records.
4. Record timestamp, checksum, retention, and the agreed RPO/RTO.

Never make a naive live-file copy while Identity is accepting writes.

## Restore drill

1. Restore into an isolated scratch volume and start an isolated Identity
   container with non-production keys and no public route.
2. Validate health and expected aggregate table counts.
3. Run `python -m identity.cli revoke-sessions`; this truncates restored
   `refresh_sessions` and `password_resets`.
4. Generate a new RS256 keypair. Update Identity's private/public keys and
   Central API's public key, then restart both services.
5. Confirm old access/refresh/reset tokens fail and a fresh admin login works.

A production restore, volume replacement, or key rotation is approval-gated.
