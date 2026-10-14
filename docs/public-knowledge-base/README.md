# Public support knowledge

Engagement 11's explicitly curated, public-only corpus. The owner-approved customer-demo plan authorizes these public policy excerpts; the rollout review must verify them before indexing/enabling hosted chat. Source references below are review provenance, not indexed content. Never copy private commercial terms, negotiated rates, staff procedures or live records here.

- `public-services.en.md`: public website FAQ and service descriptions (`uis/website/content/site.en.ts`).
- `public-delivery.en.md`: public service timeframes and peak-date caveat from `docs/company-knowledge-base/trackflow-sla-delivery.en.md`; excludes contractual compensation terms.
- `public-returns.en.md`: customer return guidance from `docs/company-knowledge-base/trackflow-returns-policy.en.md`; excludes internal inspection details and named staff.
- US/Spain public carrier names come from website FAQ; no carrier rankings, negotiated pricing or internal routing rules.

`rag-index --public` indexes only this folder into `trackflow_public`, never the internal collection. Uses existing credentials, and is a paid embedding operation: run only with owner approval. No automatic indexing during builds, startup, tests or deployment.
