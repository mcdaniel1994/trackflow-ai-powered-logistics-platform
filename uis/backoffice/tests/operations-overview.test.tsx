import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

import { OperationsOverview } from "@/components/OperationsOverview";

describe("operations overview", () => {
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

    await waitFor(() => expect(screen.getByText("Dispatched (7d)")).toBeInTheDocument());
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
});
