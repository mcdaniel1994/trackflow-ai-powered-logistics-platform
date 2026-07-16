#!/usr/bin/env bash
# Measure how long `docker compose up -d` stays attached.
#
# Coolify runs its Compose command over SSH under a bounded timeout; when that
# boundary is crossed the command dies with exit 255 and Coolify removes the
# containers during cleanup, destroying the evidence. `up -d` blocks until every
# `depends_on` condition resolves, so a long serial startup chain is charged
# against that boundary. This harness makes the attach duration observable
# locally, attributes it to a phase, and fails when it exceeds a budget.
#
# SAFETY: this script runs `down --volumes`, which destroys data. It therefore
# only ever operates on a project name it generated itself (or one you passed
# explicitly), refuses known-real project names, and never loads the repository
# .env. Point it at a disposable environment file — never production credentials.
#
# Usage:
#   scripts/release/measure_compose_startup.sh --env-file probe.env [options] [service ...]
#
#   --file FILE        Compose file under test (default: compose.coolify.yaml)
#   --env-file FILE    Disposable env file supplying the required variables (required)
#   --override FILE    Extra Compose override (repeatable)
#   --project NAME     Project name (default: a unique generated trackflow-probe-* name)
#   --budget SECONDS   Attach budget to enforce (default: 180, Coolify's approx boundary)
#   --keep             Skip teardown so containers can be inspected
#   --warm             Reuse existing volumes instead of starting from a clean slate
#
# "Cold" here means fresh volumes with images already present locally. It does
# not measure a cache-free deployment: on a real first deploy, image pull/build
# happens before any of this and is charged to the same Coolify boundary.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="compose.coolify.yaml"
ENV_FILE=""
PROJECT=""
BUDGET=180
KEEP=false
WARM=false
OVERRIDES=()
SERVICES=()

# Names this script must never act on: it would `down --volumes` real data.
readonly PROTECTED_PROJECTS=(
  "trackflow-production"
  "trackflow"
  "trackflow-local"
  "zh8uioyr9q1nvco68kvawgb5"  # Coolify resource UUID
)

die() { echo "error: $*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file) COMPOSE_FILE="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --override) OVERRIDES+=("$2"); shift 2 ;;
    --project) PROJECT="$2"; shift 2 ;;
    --budget) BUDGET="$2"; shift 2 ;;
    --keep) KEEP=true; shift ;;
    --warm) WARM=true; shift ;;
    -h|--help) sed -n '2,28p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -*) die "unknown option: $1" ;;
    *) SERVICES+=("$1"); shift ;;
  esac
done

cd "$ROOT"

# Unique by default so concurrent or repeated probes can never tear down each
# other's containers and volumes.
if [[ -z "$PROJECT" ]]; then
  PROJECT="trackflow-probe-$$-$(date +%s)"
fi
for protected in "${PROTECTED_PROJECTS[@]}"; do
  if [[ "$PROJECT" == "$protected" ]]; then
    die "refusing to operate on project '$PROJECT': this script destroys volumes."
  fi
done

[[ -n "$ENV_FILE" ]] || die "--env-file is required; point it at a disposable env file, never production."
[[ -f "$ENV_FILE" ]] || die "env file not found: $ENV_FILE"
# Never silently pick up real credentials from the repository .env.
if [[ "$(cd "$(dirname "$ENV_FILE")" && pwd)/$(basename "$ENV_FILE")" == "$ROOT/.env" ]]; then
  die "refusing to use the repository .env; copy it to a disposable file and edit the credentials."
fi

# A probe must not point at a database anyone cares about.
probe_database_url="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
if [[ -n "$probe_database_url" ]]; then
  case "$probe_database_url" in
    *localhost*|*127.0.0.1*|*example.invalid*|*@postgres:*|*@prefect-postgres:*) ;;
    *) die "DATABASE_URL in $ENV_FILE is not clearly disposable/local: refusing to start a probe against it." ;;
  esac
fi

compose_args=(--project-name "$PROJECT" --file "$COMPOSE_FILE" --env-file "$ENV_FILE")
for override in "${OVERRIDES[@]:-}"; do
  [[ -n "$override" ]] && compose_args+=(--file "$override")
done

compose() { docker compose "${compose_args[@]}" "$@"; }

REPORT_DIR="${STARTUP_PROBE_REPORT_DIR:-$(mktemp -d)}"
mkdir -p "$REPORT_DIR"
echo "Project:           $PROJECT"
echo "Report directory:  $REPORT_DIR"

# Only ever tears down this script's own generated project. It never prunes and
# never removes images, which are shared with the rest of the machine.
cleanup() {
  if [[ "$KEEP" == true ]]; then
    echo "--keep set; leaving project '$PROJECT' running. Remove it with:"
    echo "  docker compose -p $PROJECT -f $COMPOSE_FILE --env-file $ENV_FILE down --volumes"
    return
  fi
  compose down --volumes --remove-orphans --timeout 10 >/dev/null 2>&1 || true
}
trap cleanup EXIT

# A clean slate is what a first production deploy faces: an empty volume forces
# Prefect's first-boot Alembic migration onto the critical path.
if [[ "$WARM" != true ]]; then
  compose down --volumes --remove-orphans --timeout 10 >/dev/null 2>&1 || true
fi

# Record events with timestamps so each phase is separately attributable rather
# than lumped into one opaque duration.
docker events --format '{{.Time}} {{.Type}} {{.Action}} {{index .Actor.Attributes "name"}}' \
  --filter "label=com.docker.compose.project=$PROJECT" > "$REPORT_DIR/events.log" 2>/dev/null &
EVENTS_PID=$!
stop_events() { kill "$EVENTS_PID" >/dev/null 2>&1 || true; }
trap 'stop_events; cleanup' EXIT

started_at=$(date +%s)

# Enforce the budget with a watchdog rather than `timeout`, which is absent on macOS.
set +e
compose up -d --remove-orphans "${SERVICES[@]}" > "$REPORT_DIR/up.log" 2>&1 &
UP_PID=$!
(
  sleep "$BUDGET"
  if kill -0 "$UP_PID" 2>/dev/null; then
    echo "BUDGET_EXCEEDED: killing 'up -d' after ${BUDGET}s" >> "$REPORT_DIR/up.log"
    kill -TERM "$UP_PID" 2>/dev/null
  fi
) &
WATCHDOG_PID=$!
wait "$UP_PID"
UP_EXIT=$?
set -e
kill "$WATCHDOG_PID" >/dev/null 2>&1 || true

finished_at=$(date +%s)
ATTACH_SECONDS=$((finished_at - started_at))
sleep 1
stop_events

echo
echo "=================== compose up -d ==================="
cat "$REPORT_DIR/up.log"
echo "====================================================="
echo "attach_seconds=$ATTACH_SECONDS budget_seconds=$BUDGET up_exit_code=$UP_EXIT"
echo

# Per-service final state. A one-shot that never exits, or a long-running
# service stuck in `starting`, is what holds `up -d` attached.
printf '%-32s %-12s %-10s %s\n' SERVICE STATE EXIT HEALTH
for cid in $(compose ps --all --quiet 2>/dev/null); do
  docker inspect "$cid" --format \
    '{{index .Config.Labels "com.docker.compose.service"}}|{{.State.Status}}|{{.State.ExitCode}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.State.StartedAt}}|{{.State.FinishedAt}}'
done | sort | tee "$REPORT_DIR/services.txt" | while IFS='|' read -r svc state code health _started _finished; do
  printf '%-32s %-12s %-10s %s\n' "$svc" "$state" "$code" "$health"
done

# Guard logs carry the fixed tokens that name which check failed. Without these
# a failure is indistinguishable from the opaque exit 255 seen in production.
echo
for guard in prefect-postgres-bootstrap prefect-postgres-guard prefect-version-guard; do
  if compose ps --all --services 2>/dev/null | grep -qx "$guard"; then
    echo "--- $guard ---"
    compose logs --no-color --no-log-prefix "$guard" 2>&1 | tail -15
  fi
done

compose logs --no-color > "$REPORT_DIR/all-logs.txt" 2>&1 || true
echo
echo "Artifacts: $REPORT_DIR"

if [[ "$ATTACH_SECONDS" -ge "$BUDGET" ]]; then
  echo "FAIL: 'up -d' stayed attached ${ATTACH_SECONDS}s, at or over the ${BUDGET}s budget." >&2
  echo "This is the condition that ends as exit 255 under Coolify." >&2
  exit 1
fi
echo "PASS: 'up -d' returned in ${ATTACH_SECONDS}s, inside the ${BUDGET}s budget."
