import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const telemetryMocks = vi.hoisted(() => ({
  pathname: "/backoffice/telemetry/fulfilment",
  getDispatchMetrics: vi.fn(),
  getReceivingMetrics: vi.fn(),
  getStockLossMetrics: vi.fn(),
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
    telemetryMocks.getReceivingMetrics.mockResolvedValue({
      period: { from: "2026-07-01", to: "2026-07-07" },
      rows: [{ date: "2026-07-01", warehouse: "ZGZ", count: 8 }],
    });
    telemetryMocks.getStockLossMetrics.mockResolvedValue({
      period: { from: "2026-07-01", to: "2026-07-07" },
      rows: [{ date: "2026-07-01", warehouse: "LA", count: 2, units: 9 }],
    });
    telemetryMocks.getAccessDenialMetrics.mockResolvedValue({
      period: { from: "2026-07-01", to: "2026-07-07" },
      rows: [{ date: "2026-07-01", reason: "unauthenticated", count: 3 }],
    });
  });

  it("renders exact dispatch/receiving figures and labels rejections as diagnostic", async () => {
    render(<FulfilmentView />);

    await waitFor(() => expect(screen.getByText("Dispatch by day and warehouse")).toBeInTheDocument());
    // Exact dispatched total and best-effort rejected total appear as stat cards.
    expect(screen.getByText("Dispatched (exact)")).toBeInTheDocument();
    expect(screen.getByText("Rejected (diagnostic)")).toBeInTheDocument();
    expect(screen.getByText("20.0%")).toBeInTheDocument(); // indicative failure rate
    expect(screen.getAllByText(/Best-effort diagnostic — may undercount/i).length).toBeGreaterThan(0);
  });

  it("shows the security view with denials, stock loss, and an Identity-logs note", async () => {
    render(<SecurityView />);

    await waitFor(() => expect(screen.getByText("API access denials by day and reason")).toBeInTheDocument());
    expect(screen.getByText("Unauthenticated")).toBeInTheDocument();
    expect(screen.getByText("Stock loss by day and warehouse")).toBeInTheDocument();
    expect(screen.getByText(/Login auditing is kept in Identity's safe logs/i)).toBeInTheDocument();
  });

  it("renders an empty state when a metric has no rows", async () => {
    telemetryMocks.getDispatchMetrics.mockResolvedValue({
      period: { from: "2026-07-01", to: "2026-07-07" },
      rows: [],
    });
    render(<FulfilmentView />);

    await waitFor(() =>
      expect(screen.getByText("No dispatch telemetry in this range.")).toBeInTheDocument(),
    );
  });

  it("surfaces a friendly error when a metric request fails", async () => {
    telemetryMocks.getAccessDenialMetrics.mockRejectedValue({ message: "Telemetry service is temporarily unavailable.", status: 503 });
    render(<SecurityView />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/temporarily unavailable/i));
  });

  it("marks the active telemetry section in the sub-navigation", () => {
    telemetryMocks.pathname = "/backoffice/telemetry/security";
    render(<TelemetryPageHeader eyebrow="Telemetry" title="Security" description="test" />);

    const active = screen.getByRole("link", { name: /Security/i });
    expect(active).toHaveAttribute("aria-current", "page");
  });
});
