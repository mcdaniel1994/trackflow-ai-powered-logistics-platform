import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const overviewMocks = vi.hoisted(() => ({
  getDispatchMetrics: vi.fn(),
  getReceivingMetrics: vi.fn(),
  getStockLossMetrics: vi.fn(),
  listMovements: vi.fn(),
}));

vi.mock("@/lib/telemetry/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/telemetry/api")>("@/lib/telemetry/api");
  return {
    ...actual,
    getDispatchMetrics: overviewMocks.getDispatchMetrics,
    getReceivingMetrics: overviewMocks.getReceivingMetrics,
    getStockLossMetrics: overviewMocks.getStockLossMetrics,
  };
});

vi.mock("@/lib/inventory/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/inventory/api")>("@/lib/inventory/api");
  return { ...actual, listMovements: overviewMocks.listMovements };
});

import { FulfilmentOperationsView } from "@/components/operations/FulfilmentOperationsView";
import { OperationsOverview } from "@/components/OperationsOverview";

describe("operations overview", () => {
  afterEach(() => { cleanup(); vi.useRealTimers(); });
  beforeEach(() => {
    vi.clearAllMocks();
    overviewMocks.getDispatchMetrics.mockResolvedValue({
      period: { from: "2026-07-06", to: "2026-07-13" },
      rows: [{ date: "2026-07-13", warehouse: "LA", dispatched: 12, rejected: 1, indicative_failure_rate: 0.08 }],
    });
    overviewMocks.getReceivingMetrics.mockResolvedValue({
      period: { from: "2026-07-06", to: "2026-07-13" },
      rows: [{ date: "2026-07-13", warehouse: "ZGZ", count: 7 }],
    });
    overviewMocks.getStockLossMetrics.mockResolvedValue({
      period: { from: "2026-07-06", to: "2026-07-13" },
      rows: [{ date: "2026-07-13", warehouse: "LA", count: 1, units: 4 }],
    });
    overviewMocks.listMovements.mockResolvedValue({
      items: [
        {
          id: 42,
          movement_type: "outbound",
          sku_id: 3,
          quantity: 5,
          reference: null,
          exit_type: "dispatch",
          tracking_number: "1Z999",
          warehouse: "LA",
          created_at: new Date().toISOString(),
          user_uuid: "svc-uuid",
          sku: { id: 3, name: "Sneaker", sku: "CLT-SNK", client_name: "PureStep", category: "fashion", warehouse: "LA" },
        },
      ],
      total: 1,
      limit: 8,
      offset: 0,
    });
  });

  it("renders live exact totals and a recent-activity strip", async () => {
    render(<OperationsOverview />);

    await waitFor(() => expect(screen.getByText("12")).toBeInTheDocument());
    expect(screen.getByText("12")).toBeInTheDocument(); // exact dispatched total
    expect(screen.getByText("Received (7d)")).toBeInTheDocument();
    expect(screen.getByText("Recent activity")).toBeInTheDocument();
    expect(screen.getByText("Dispatched")).toBeInTheDocument();
    expect(screen.getByText("CLT-SNK", { exact: false })).toBeInTheDocument();
    // Best-effort language never claims false precision on the overview KPIs.
    expect(screen.getByText(/system of record/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Fulfilment details/i })).toHaveAttribute(
      "href",
      "/backoffice/operations/fulfilment",
    );
    expect(screen.getByRole("link", { name: /Stock loss details/i })).toHaveAttribute(
      "href",
      "/backoffice/operations/stock-loss",
    );
  });

  it("surfaces a friendly error when the live feed cannot be read", async () => {
    overviewMocks.getDispatchMetrics.mockRejectedValue({
      message: "Telemetry service is temporarily unavailable.",
      status: 503,
    });
    render(<OperationsOverview />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/temporarily unavailable/i));
  });
  it("renders other metrics immediately when dispatch fails, with a placeholder rather than zero", async () => {
    overviewMocks.getDispatchMetrics.mockRejectedValue({ status: 503, message: "Telemetry service is temporarily unavailable." });
    render(<OperationsOverview />);
    await screen.findByText("7");
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("CLT-SNK", { exact: false })).toBeInTheDocument();
    const card = screen.getByText("Dispatched (7d)").closest("article")!;
    expect(within(card).getByText("—")).toBeInTheDocument();
    expect(within(card).queryByText("0")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Partial data · retrying");
  });

  it("shows genuine empty results as zero/empty and marks all-success data Live", async () => {
    for (const mock of [overviewMocks.getDispatchMetrics, overviewMocks.getReceivingMetrics, overviewMocks.getStockLossMetrics]) mock.mockResolvedValue({ rows: [] });
    overviewMocks.listMovements.mockResolvedValue({ items: [] });
    render(<OperationsOverview />);
    await screen.findByText("No recent movements yet.");
    expect(screen.getAllByText("0")).toHaveLength(3);
    expect(screen.getByRole("status")).toHaveTextContent(/^Live$/);
  });

  it("keeps successful data on a failed refresh, marks it stale, and recovers without a page refresh", async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    overviewMocks.getDispatchMetrics.mockResolvedValueOnce({ rows: [{ dispatched: 12 }] }).mockRejectedValueOnce({ status: 503, message: "Unavailable" }).mockResolvedValue({ rows: [{ dispatched: 13 }] });
    render(<OperationsOverview />);
    await act(async () => {});
    expect(screen.getByRole("status")).toHaveTextContent(/^Live$/);
    await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText(/Stale — last successful update/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Partial data · retrying");
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(screen.getByText("13")).toBeInTheDocument();
    expect(screen.queryByText(/Stale —/)).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/^Live$/);
    vi.restoreAllMocks();
  });

  it("does not claim Live after 60s without a successful update", async () => {
    vi.useFakeTimers();
    render(<OperationsOverview />);
    await act(async () => {});
    expect(screen.getByRole("status")).toHaveTextContent(/^Live$/);
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(screen.getByRole("status")).toHaveTextContent("Partial data");
    expect(screen.getAllByText(/Stale — last successful update/)).toHaveLength(4);
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
  });

  it("shows unavailable/retrying when every initial request fails", async () => {
    for (const mock of Object.values(overviewMocks)) mock.mockRejectedValue({ status: 503, message: "Unavailable" });
    render(<OperationsOverview />);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Unavailable · retrying"));
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.queryByText("No recent movements yet.")).not.toBeInTheDocument();
  });

  it("loads fulfilment resources independently and clears old totals and tables on range change", async () => {
    overviewMocks.getReceivingMetrics.mockRejectedValue({ status: 503, message: "Unavailable" });
    const { unmount } = render(<FulfilmentOperationsView />);
    await screen.findByText("Dispatch by day and warehouse");
    expect(screen.queryByText("Receiving by day and warehouse")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Receiving: Unavailable");
    expect(screen.getByRole("status")).toHaveTextContent("Partial data");
    const signals: AbortSignal[] = [];
    overviewMocks.getDispatchMetrics.mockImplementation((_range, signal) => { signals.push(signal); return new Promise(() => {}); });
    overviewMocks.getReceivingMetrics.mockImplementation((_range, signal) => { signals.push(signal); return new Promise(() => {}); });
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-07-07" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(screen.queryByText("Dispatch by day and warehouse")).not.toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2);
    expect(screen.getByRole("status")).toHaveTextContent("Connecting…");
    expect(overviewMocks.getDispatchMetrics).toHaveBeenLastCalledWith({ from: "2026-07-01", to: "2026-07-07" }, expect.any(AbortSignal));
    unmount();
    expect(signals.every((signal) => signal.aborted)).toBe(true);
  });

});
