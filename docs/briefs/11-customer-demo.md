# Brief: Customer Chat, Readable History & Careers Demo

## Client: TrackFlow · Stakeholder: Cory McDaniel (Portfolio Owner)

## Status

Local implementation verified — Engagement 11, October 13, 2026. All three owner-authorized phases are implemented with mocked regression and browser checks. October 14 owner authorization extended to local setup, paid public indexing/provider verification and fictional sandbox writes; all passed. Hosted deployment remains separately gated. See [release evidence](../planning/remaining_planning/spec-11-customer-demo.md#local-release-evidence) and [rollout](../runbooks/customer-demo.md).

October 14 preview correction: footer-safe launcher positioning, static greetings and explicit
disabled-policy feedback address owner-reported UI defects. Local live AI subsequently enabled and verified; hosted rollout remains unexecuted.

October 14 owner privacy correction: Admin Demo card/autofill now use `admin@trackflow.com`;
matching local Identity login verified with the same account ID and history ownership. Hosted
Identity maintenance remains part of the deferred rollout.

CI follow-up: auth-test UTC aliases corrected; package lint/types/build and 20 tests pass locally.
All nine remote release-check jobs passed on the prior run. The public corpus is now allowlisted
in `.dockerignore`; a complete local Linux AMD64 Central API image build and corpus inspection passed.

## Background

The Engagement 7–10 assistant serves employees in the authenticated Back Office. Its CX label is ambiguous, saved chat entries show only dates, and the public website has no customer chat or careers entry point. The existing talent sandbox already supports candidate management.

## Stakeholder Request

> Rename the employee-facing chat TrackFlow Assistant and show words/topic instead of only the time. Add TrackFlow Support for public policy questions. Add a Careers footer link with generic roles and a working fictional application form so I can demonstrate the application appearing in the Talent Pipeline Tracker.

## Assignment

Implement the owner-approved [specification](../planning/remaining_planning/spec-11-customer-demo.md) in three reviewable phases. Authorization covers all three phases locally, overriding a pause between phases for this request. Reuse existing AI credentials and the talent sandbox; introduce no applicant database.

## What You're Building

1. Employee-facing TrackFlow Assistant copy and response-only first-user-message conversation titles, owner-scoped and compatible with existing history.
2. Bilingual Careers page and fictional applications written to the same sandbox consumed by the Back Office, with a confirmed-record link, generic tracker heading and refresh.
3. Public TrackFlow Support panel and private knowledge-only backend, bounded usage and deadlines, isolated public corpus, fixed authenticated gateway, off by default.

## Acceptance Criteria

- Titles survive reload, use the earliest persisted user question, and never expose another owner's data or reach telemetry.
- Website chat answers only from curated public policies, with separate language and US/Spain choices, no tools or internal memory, and tested input/output guardrails.
- The Careers demo accepts fictional information and example.com email only, creates received/pending candidates, and links to the authenticated record; success requires confirmed creation.
- Failure paths, limits, accessibility, metadata and the application-to-tracker journey are tested. Every touched app/package/service passes its release checks with coverage preserved.
- Tracking docs and rollout instructions distinguish local evidence from unexecuted live verification.

## Out of Scope

Real applicants, customer identity verification, shipment tracking integration, return actions, persistent public chat, production deployment, paid AI calls, new provider keys, applicant database and changes to delivered technical agent IDs.
