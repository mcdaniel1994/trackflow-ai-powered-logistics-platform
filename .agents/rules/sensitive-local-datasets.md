# Sensitive Local Datasets

## Rule Name

Sensitive Local Datasets

## Scope

File-pattern based.

## Applies When

Any task, exploration, command, script, test, or documentation work would read, print, copy, summarize, export, transform, or otherwise inspect:

- `scripts/incidents-trackflow.csv`
- Any future file explicitly documented as a sensitive local dataset

## Required Behavior

- Treat `scripts/incidents-trackflow.csv` as sensitive customer data because it may contain real customer email addresses.
- Remember that `.gitignore` prevents commits, but it does not prevent local reads by agents or tools.
- Do not inspect the sensitive file opportunistically during repo exploration, debugging, search, test setup, or validation.
- Prefer safe fixtures, aggregate-only outputs, or user-provided summaries by default.
- Use `services/incident-processor/tests/fixtures/sample-incidents.csv` for development, tests, examples, and verification unless the user explicitly authorizes the real dataset.
- Access the sensitive file only when the user explicitly names the file and grants permission to read it for the current task.
- If sensitive-file access is genuinely required and has not already been authorized for the current task, ask for explicit confirmation before reading it.
- Never include raw rows, customer emails, offending field values, or copied sensitive content in agent messages, logs, generated docs, generated tests, exports, screenshots, or copied files.
- If an aggregate command is authorized against the sensitive file, report only aggregate metrics and safe validation identifiers such as row number, field, and rule code.

## Examples

- The user says, "Run the incident processor against `scripts/incidents-trackflow.csv` and tell me the aggregate totals." The agent may run the aggregate command and report only aggregate results.
- The user says, "Debug why the real CSV fails, but do not show any private values." The agent must ask for explicit confirmation before reading the file, then avoid printing raw rows or values.
- A test needs incident data. Use `services/incident-processor/tests/fixtures/sample-incidents.csv`, not the sensitive local CSV.

## Non-Examples

- Running `cat scripts/incidents-trackflow.csv` during exploration.
- Searching the sensitive CSV with `rg`, `grep`, `awk`, Python, or similar tools to inspect row content without explicit authorization.
- Copying rows from the sensitive CSV into tests, docs, prompts, screenshots, logs, or exported files.
- Printing validation errors that include the offending email address or full row.

