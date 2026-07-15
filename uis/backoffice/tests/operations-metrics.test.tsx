import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const operationsMocks = vi.hoisted(() => ({
  pathname: "/backoffice/operations/fulfilment",
  getDispatchMetrics: vi.fn(),
  getReceivingMetrics: vi.fn(),
  getStockLossMetrics: vi.fn(),
}));

vi.mock("next/navigation", () => ({ usePathname: () => operationsMocks.pathname }));
vi.mock("@/lib/telemetry/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/telemetry/api")>("@/lib/telemetry/api");
  return { ...actual, ...operationsMocks };
});

import { FulfilmentOperationsView } from "@/components/operations/FulfilmentOperationsView";
import { StockLossOperationsView } from "@/components/operations/StockLossOperationsView";

describe("operations exact metrics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    operationsMocks.pathname = "/backoffice/operations/fulfilment";
    operationsMocks.getDispatchMetrics.mockResolvedValue({ period: { from: "2026-07-01", to: "2026-07-07" }, rows: [{ date: "2026-07-01", warehouse: "LA", dispatched: 20, rejected: 5, indicative_failure_rate: 0.2 }] });
    operationsMocks.getReceivingMetrics.mockResolvedValue({ period: { from: "2026-07-01", to: "2026-07-07" }, rows: [{ date: "2026-07-01", warehouse: "ZGZ", count: 8 }] });
    operationsMocks.getStockLossMetrics.mockResolvedValue({ period: { from: "2026-07-01", to: "2026-07-07" }, rows: [{ date: "2026-07-01", warehouse: "LA", count: 2, units: 9 }] });
  });

  it("renders exact fulfilment metrics without diagnostic figures", async () => {
    render(<FulfilmentOperationsView />);
    await waitFor(() => expect(screen.getByText("Dispatch by day and warehouse")).toBeInTheDocument());
    expect(screen.getByText("Dispatched (exact)")).toBeInTheDocument();
    expect(screen.getByText("Received (exact)")).toBeInTheDocument();
    expect(screen.queryByText(/Rejected/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Indicative failure rate/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fulfilment" })).toHaveAttribute("aria-current", "page");
  });

  it("renders exact stock-loss metrics without security diagnostics", async () => {
    operationsMocks.pathname = "/backoffice/operations/stock-loss";
    render(<StockLossOperationsView />);
    await waitFor(() => expect(screen.getByText("Stock loss by day and warehouse")).toBeInTheDocument());
    expect(screen.getByText("Stock loss units (exact)")).toBeInTheDocument();
    expect(screen.queryByText(/Access denials/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Stock loss" })).toHaveAttribute("aria-current", "page");
  });
});
