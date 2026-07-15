# Production release helpers

`coolify_release.py` is the fail-closed image mutation and deployment poller used by the
approval-protected production workflow. It changes only the production
`TRACKFLOW_IMAGE_TAG`, preserves all other Coolify environment records and metadata, and
accepts only immutable `sha-<40 hex>` targets and rollback tags. It never prints tokens,
webhooks, application coordinates, environment values, or response bodies.
