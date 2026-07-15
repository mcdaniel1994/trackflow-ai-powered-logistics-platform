import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const telemetryMocks = vi.hoisted(() => ({
  pathname: "/backoffice/telemetry/fulfilment",
  getDispatchMetrics: vi.fn(),
  getAccessDenialMetrics: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => telemetryMocks.pathname,
}));

vi.mock("@/lib/telemetry/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/telemetry/api")>("@/lib/telemetry/api");
  return { ...actual, ...telemetryMocks };
});

import { FulfilmentView } from "@/components/telemetry/FulfilmentView";
import { SecurityView } from "@/components/telemetry/SecurityView";
import { TelemetryPageHeader } from "@/components/telemetry/TelemetryPageHeader";

describe("telemetry UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    telemetryMocks.pathname = "/backoffice/telemetry/fulfilment";
    telemetryMocks.getDispatchMetrics.mockResolvedValue({
      period: { from: "2026-07-01", to: "2026-07-07" },
      rows: [{ date: "2026-07-01", warehouse: "LA", dispatched: 20, rejected: 5, indicative_failure_rate: 0.2 }],
    });
    telemetryMocks.getAccessDenialMetrics.mockResolvedValue({
      period: { from: "2026-07-01", to: "2026-07-07" },
      rows: [{ date: "2026-07-01", reason: "unauthenticated", count: 3 }],
    });
  });

  it("renders rejected-dispatch diagnostics without exact business metrics", async () => {
    render(<FulfilmentView />);

    await waitFor(() => expect(screen.getByText("Rejected dispatches by day and warehouse")).toBeInTheDocument());
    expect(screen.getByText("Rejected (diagnostic)")).toBeInTheDocument();
    expect(screen.getByText("20.0%")).toBeInTheDocument(); // indicative failure rate
    expect(screen.getAllByText(/Best-effort diagnostic — may undercount/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("Dispatched (exact)")).not.toBeInTheDocument();
    expect(screen.queryByText("Received (exact)")).not.toBeInTheDocument();
    expect(screen.queryByText("Receiving by day and warehouse")).not.toBeInTheDocument();
  });

  it("shows security diagnostics without exact stock-loss metrics", async () => {
    telemetryMocks.pathname = "/backoffice/telemetry/security";
    render(<SecurityView />);

    await waitFor(() => expect(screen.getByText("API access denials by day and reason")).toBeInTheDocument());
    expect(screen.getByText("Unauthenticated")).toBeInTheDocument();
    expect(screen.queryByText("Stock loss by day and warehouse")).not.toBeInTheDocument();
    expect(screen.queryByText("Stock loss units (exact)")).not.toBeInTheDocument();
    expect(screen.getByText(/Login auditing remains in Identity's safe logs/i)).toBeInTheDocument();
  });

  it("renders an empty state when a metric has no rows", async () => {
    telemetryMocks.getDispatchMetrics.mockResolvedValue({
      period: { from: "2026-07-01", to: "2026-07-07" },
      rows: [],
    });
    render(<FulfilmentView />);

    await waitFor(() =>
      expect(screen.getByText("No rejected-dispatch diagnostics in this range.")).toBeInTheDocument(),
    );
  });

  it("surfaces a friendly error when a metric request fails", async () => {
    telemetryMocks.getAccessDenialMetrics.mockRejectedValue({ message: "Telemetry service is temporarily unavailable.", status: 503 });
    render(<SecurityView />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/temporarily unavailable/i));
  });

  it("marks the active telemetry section in the sub-navigation", () => {
    telemetryMocks.pathname = "/backoffice/telemetry/security";
    render(<TelemetryPageHeader eyebrow="Technical telemetry" title="Security diagnostics" description="test" />);

    const active = screen.getByRole("link", { name: /Security diagnostics/i });
    expect(active).toHaveAttribute("aria-current", "page");
  });
});
