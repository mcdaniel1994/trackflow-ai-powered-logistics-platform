import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const reportingMocks = vi.hoisted(() => ({
  role: "admin" as "admin" | "user",
  getWeeklyPerformance: vi.fn(),
  getPipelineRunsStatus: vi.fn(),
  requestPipelineRun: vi.fn(),
}));

vi.mock("@/lib/auth/context", () => ({
  useAuth: () => ({ user: { role: reportingMocks.role } }),
}));

vi.mock("@/lib/reporting/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/reporting/api")>("@/lib/reporting/api");
  return { ...actual, ...reportingMocks };
});

import { BusinessReportingView } from "@/components/reporting/BusinessReportingView";

const report = {
  week_start: "2026-07-13",
  incomplete: true,
  entries: [
    {
      warehouse: "los_angeles" as const,
      client_id: "11111111-1111-4111-8111-111111111111",
      client_name: "Fashion Co",
      inbound_units_count: 4200,
      outbound_orders_count: 980,
      stockout_events_count: 3,
      discrepancy_events_count: 2,
      discrepancy_rate: 0.002,
    },
  ],
};

const status = {
  latest: {
    run_id: "run-current",
    status: "failed" as const,
    trigger_type: "scheduled" as const,
    requested_by: "system",
    scheduled_business_date: "2026-07-14",
    requested_at: "2026-07-14T12:00:00Z",
    started_at: "2026-07-14T12:01:00Z",
    finished_at: "2026-07-14T12:02:00Z",
    attempt: 1,
    rows_loaded: null,
    error_code: "LOAD_FAILED",
    next_attempt_at: null,
  },
  queued: [{ run_id: "queued-1", trigger_type: "manual" as const, requested_at: "2026-07-14T12:03:00Z" }],
  latest_successful: {
    run_id: "run-success",
    finished_at: "2020-01-01T12:00:00Z",
    target_weeks: ["2026-07-13"],
    rows_loaded: 24,
  },
  queue_state: "queued" as const,
  worker: {
    status: "healthy" as const,
    last_seen_at: "2026-07-14T12:04:00Z",
    last_progress_at: "2026-07-14T12:04:00Z",
    orchestrator_healthy: true,
  },
  next_scheduled_refresh: {
    local_time: "07:00" as const,
    timezone: "America/Chicago" as const,
    next_occurrence_utc: "2026-07-15T12:00:00Z",
  },
};

describe("business reporting dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    reportingMocks.role = "admin";
    reportingMocks.getWeeklyPerformance.mockResolvedValue(report);
    reportingMocks.getPipelineRunsStatus.mockResolvedValue(status);
    reportingMocks.requestPipelineRun.mockResolvedValue({ run_id: "queued-run", status: "requested" });
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("renders KPI contracts, client display names, incomplete status, and safe run metadata", async () => {
    render(<BusinessReportingView />);

    expect(await screen.findByText("Fashion Co")).toBeInTheDocument();
    expect(screen.getAllByText("Inbound units")).toHaveLength(2);
    expect(screen.getAllByText("Outbound orders")).toHaveLength(2);
    expect(screen.getAllByText("Stockout events")).toHaveLength(2);
    expect(screen.getAllByText("Discrepancy events")).toHaveLength(2);
    expect(screen.getByText("0.20%")).toBeInTheDocument();
    expect(screen.getByText("Incomplete — ledger reset mid-week")).toBeInTheDocument();
    expect(screen.getByText("1 queued")).toBeInTheDocument();
    expect(screen.getByText("Failure: LOAD_FAILED")).toBeInTheDocument();
    expect(screen.getByText("7:00 AM (America/Chicago)")).toBeInTheDocument();
    expect(screen.getByText(/stale/i)).toBeInTheDocument();
    expect(screen.queryByText(report.entries[0].client_id)).not.toBeInTheDocument();
    expect(document.body.textContent?.toLowerCase()).not.toMatch(/r2|cache_nonce|object key|bucket/);
  });

  it("queues normal and force-refresh requests and then polls status", async () => {
    const user = userEvent.setup();
    render(<BusinessReportingView />);
    await screen.findByText("Fashion Co");

    await user.click(screen.getByRole("button", { name: "Run now" }));
    await waitFor(() => expect(reportingMocks.requestPipelineRun).toHaveBeenCalledWith({ force_refresh: false }));
    expect(await screen.findByRole("status")).toHaveTextContent("queued-run");

    await user.click(screen.getByRole("button", { name: "Force refresh" }));
    await waitFor(() => expect(reportingMocks.requestPipelineRun).toHaveBeenCalledWith({ force_refresh: true }));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/recomputes directly from source records/i));
  });

  it("validates Monday selection and loads an explicit week", async () => {
    const user = userEvent.setup();
    render(<BusinessReportingView />);
    await screen.findByText("Fashion Co");

    const picker = screen.getByLabelText("Report week (Monday)");
    fireEvent.change(picker, { target: { value: "2026-07-14" } });
    await user.click(screen.getByRole("button", { name: "Load week" }));
    expect(screen.getByText(/choose a monday/i)).toBeInTheDocument();

    fireEvent.change(picker, { target: { value: "2026-07-20" } });
    await user.click(screen.getByRole("button", { name: "Load week" }));
    await waitFor(() => expect(reportingMocks.getWeeklyPerformance).toHaveBeenCalledWith("2026-07-20"));
  });

  it("hides administrator controls from standard users and renders the empty state", async () => {
    reportingMocks.role = "user";
    reportingMocks.getWeeklyPerformance.mockResolvedValue({ week_start: "2026-07-13", incomplete: false, entries: [] });
    render(<BusinessReportingView />);
    expect(await screen.findByText("No report computed yet for this week")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run now" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Force refresh" })).not.toBeInTheDocument();
  });

  it.each(["idle", "processing", "queued", "retrying", "stuck", "unavailable"] as const)(
    "renders the server-derived %s queue state",
    async (queueState) => {
    reportingMocks.getPipelineRunsStatus.mockResolvedValue({
      ...status,
      queue_state: queueState,
      latest: {
        ...status.latest,
        status: queueState === "retrying" ? "retryable" : status.latest.status,
        next_attempt_at: queueState === "retrying" ? "2026-07-15T12:30:00Z" : null,
      },
    });
    render(<BusinessReportingView />);
    expect(await screen.findByText(queueState, { selector: "span" })).toBeInTheDocument();
    if (queueState === "retrying") {
      expect(screen.getByText(/attempt 1 of 5, next try at/i)).toBeInTheDocument();
    }
  });

  it("shows an initial loading state while reporting requests are pending", () => {
    reportingMocks.getWeeklyPerformance.mockReturnValue(new Promise(() => undefined));
    reportingMocks.getPipelineRunsStatus.mockReturnValue(new Promise(() => undefined));
    render(<BusinessReportingView />);
    expect(screen.getByText("Loading business reporting…")).toBeInTheDocument();
  });

  it("surfaces a safe loading failure", async () => {
    reportingMocks.getWeeklyPerformance.mockRejectedValue({ message: "Reporting service is temporarily unavailable.", status: 503 });
    render(<BusinessReportingView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Reporting service is temporarily unavailable.");
  });

  it("warns when queued work has no healthy worker", async () => {
    reportingMocks.getPipelineRunsStatus.mockResolvedValue({
      ...status,
      queue_state: "unavailable",
      worker: {
        status: "stale",
        last_seen_at: "2026-07-14T12:00:00Z",
        last_progress_at: "2026-07-14T12:00:00Z",
        orchestrator_healthy: false,
      },
    });
    render(<BusinessReportingView />);
    expect(await screen.findByText(/worker or orchestrator is not responding/i)).toBeInTheDocument();
  });
});
