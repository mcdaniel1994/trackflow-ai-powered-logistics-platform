import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiscrepancyRateChart } from "@/components/reporting/charts/DiscrepancyRateChart";
import { GroupedBarChart } from "@/components/reporting/charts/GroupedBarChart";
import { KpiTiles } from "@/components/reporting/charts/KpiTiles";
import { SERIES_LIGHT } from "@/components/reporting/charts/palette";
import type { WeeklyPerformanceEntry } from "@/lib/reporting/types";

function entry(overrides: Partial<WeeklyPerformanceEntry>): WeeklyPerformanceEntry {
  return {
    warehouse: "los_angeles",
    client_id: "c",
    client_name: "Client",
    inbound_units_count: 0,
    outbound_orders_count: 0,
    stockout_events_count: 0,
    discrepancy_events_count: 0,
    discrepancy_rate: 0,
    ...overrides,
  };
}

const week: WeeklyPerformanceEntry[] = [
  entry({ warehouse: "los_angeles", client_name: "Alpha", outbound_orders_count: 100, inbound_units_count: 500, discrepancy_rate: 0.01 }),
  entry({ warehouse: "zaragoza", client_name: "Alpha", outbound_orders_count: 60, inbound_units_count: 200, discrepancy_rate: 0.02 }),
  entry({ warehouse: "los_angeles", client_name: "Beta", outbound_orders_count: 40, inbound_units_count: 300, discrepancy_rate: 0.05 }),
];

describe("reporting charts", () => {
  it("KpiTiles sums each metric across entries", () => {
    render(<KpiTiles entries={week} />);
    // Inbound units total: 500 + 200 + 300 = 1,000
    expect(screen.getByText("1,000")).toBeInTheDocument();
    // Outbound orders total: 100 + 60 + 40 = 200
    expect(screen.getByText("200")).toBeInTheDocument();
  });

  it("GroupedBarChart renders one mark per client × warehouse and a two-series legend", () => {
    const { container } = render(
      <GroupedBarChart title="Outbound orders by client" entries={week} metric="outbound_orders_count" />,
    );
    // 2 clients × 2 warehouses = 4 bar marks.
    expect(container.querySelectorAll("rect")).toHaveLength(4);
    const legend = screen.getByRole("list");
    expect(within(legend).getByText("Los Angeles")).toBeInTheDocument();
    expect(within(legend).getByText("Zaragoza")).toBeInTheDocument();
  });

  it("GroupedBarChart assigns a stable color per warehouse regardless of the clients present", () => {
    const { container } = render(
      <GroupedBarChart title="Outbound orders by client" entries={week} metric="outbound_orders_count" />,
    );
    const fills = Array.from(container.querySelectorAll("rect")).map((rect) => rect.getAttribute("fill"));
    // Los Angeles is always slot 0, Zaragoza always slot 1 (light palette here).
    expect(fills).toContain(SERIES_LIGHT[0]);
    expect(fills).toContain(SERIES_LIGHT[1]);
    expect(fills).not.toContain(SERIES_LIGHT[2]); // never generate extra hues
  });

  it("GroupedBarChart shows an empty state for a week with no entries", () => {
    render(<GroupedBarChart title="Outbound orders by client" entries={[]} metric="outbound_orders_count" />);
    expect(screen.getByText(/No client activity/i)).toBeInTheDocument();
  });

  it("DiscrepancyRateChart formats percentages and sorts worst-first", () => {
    const { container } = render(<DiscrepancyRateChart entries={week} />);
    // Beta 5.0% > Alpha mean (1% and 2% → 1.5%).
    const labels = Array.from(container.querySelectorAll("text"))
      .map((node) => node.textContent)
      .filter((text) => text?.endsWith("%"));
    expect(labels[0]).toBe("5.0%");
    expect(labels).toContain("1.5%");
  });

  it("DiscrepancyRateChart shows an empty state with no entries", () => {
    render(<DiscrepancyRateChart entries={[]} />);
    expect(screen.getByText(/No client activity/i)).toBeInTheDocument();
  });
});
