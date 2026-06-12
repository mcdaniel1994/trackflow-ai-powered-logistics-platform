# TrackFlow Incident Report Processor

**Status:** Subproject planning and implementation spec — not an engagement brief  
**Stakeholder:** Valentina Cruz, CX Manager  
**Primary implementation paths:** `services/incident-processor/`, `scripts/analyze.py`, `uis/backoffice/app/incidents/`

---

## Purpose

The Incident Report Processor gives TrackFlow Customer Experience an internal way to analyze one month of incident exports from the legacy helpdesk before first-line support automation is built.

This is a TrackFlow subproject, not Engagement 5. Engagement 5 remains reserved for the future Central API unless a later roadmap decision changes it.

## Stakeholder Request

Valentina Cruz, CX Manager, asked for the incident analysis to show operational volume, data quality, country split, category concentration, and satisfaction without exposing customer email addresses:

> The satisfaction scores for logistics are always lower than average — that's normal in our sector. What I need to understand is whether the problem is more severe in the US or Spain, and whether it's concentrated in specific categories like `DELAYED_DELIVERY` or `LOST_PARCEL`. The breakdown by country is important to me: include it in the console output even if it's not in the main spec. The CSV export should have one row per metric — I'll use it in the client report. And same as always — no customer emails in any output, ever.

## Data Contract

Input CSV files use UTF-8, comma separation, and a header row. Required fields are:

- `incident_id`
- `date`
- `country`
- `customer_type`
- `tracking_number`
- `carrier`
- `category`
- `description`
- `status`
- `customer_email`
- `satisfaction_score`

The official local file belongs at `scripts/incidents-trackflow.csv` and must not be committed.

## Validation Rules

Trim surrounding whitespace before validation, but require canonical casing for controlled values. Do not silently convert lowercase values to uppercase.

- `incident_id`: exact `TRF-XXXXXX` format and unique within the file
- `date`: exact valid `YYYY-MM-DD`
- `country`: `US` or `ES`
- `customer_type`: `B2B` or `B2C`
- `tracking_number`: at least 8 characters
- `carrier`: valid for the declared country
- `category`: `LOST_PARCEL`, `DELAYED_DELIVERY`, `WRONG_ADDRESS`, `RETURN_REQUEST`, or `DAMAGE`
- `description`: at least 5 characters
- `status`: `OPEN`, `CLOSED`, or `DISCARDED`
- `customer_email`: non-empty and contains `@`
- `satisfaction_score`: integer 1-5 when present; required when `status` is `CLOSED`

`invalid_records` is the number of unique rows with at least one violation. Each triggered rule increments its own counter, so one row may increment multiple rule counters. Invalid rows are excluded from category, status, country, and satisfaction metrics.

Ignore only non-record trailing empty lines from file formatting. A parsed blank row inside the dataset is an invalid record.

## Runtime Surfaces

### CLI

Supported commands:

```bash
python scripts/analyze.py scripts/incidents-trackflow.csv
uv run --project services/incident-processor analyze scripts/incidents-trackflow.csv
```

The CLI prints the aggregate report and can export deterministic metric rows to CSV.

### FastAPI

The service lives at `services/incident-processor/` and exposes:

- `GET /health`
- `POST /api/incidents/analyze`
- `GET /api/incidents/results/export`

The API stores the latest aggregate analysis in a single in-memory `app.state` slot. This is demo-grade storage: last-write-wins, cleared on restart, and intended for one worker only.

CORS uses `INCIDENT_PROCESSOR_CORS_ORIGINS`, defaulting to:

- `http://localhost:3000`
- `http://127.0.0.1:3000`

### Backoffice UI

The interface lives in the existing backoffice app at:

```text
uis/backoffice/app/incidents/page.tsx
```

It calls the incident processor API through `uis/backoffice/lib/incident-api.ts` and renders only aggregate, safe metrics.

## Privacy Requirements

Customer emails may be read only for validation. They must never appear in:

- console output
- logs
- JSON responses
- error messages
- UI-facing data
- CSV exports

Validation errors may include only row number, field, and safe rule code.

## Export Contract

Exports use deterministic one-row-per-metric CSV with stable columns:

```text
section,metric,value,percentage
```

Rows are ordered consistently with the console report: summary, invalid rule counters, category, status, country, and satisfaction.

