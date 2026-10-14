# Careers demo

`CareersPage` renders illustrative roles and a bilingual fictional application form. Role buttons
preselect the shared allowlisted role; sample fill supplies example.com data. Success requires the
server's confirmed candidate ID. The form prevents concurrent submissions and explains ambiguous
writes without automatically retrying. No phone, uploads or personal URLs are collected.

Validation lives in `lib/careers.ts`; the server route owns the sandbox adapter. See
[the website README](../../README.md) and [rollout](../../../../docs/runbooks/customer-demo.md).
