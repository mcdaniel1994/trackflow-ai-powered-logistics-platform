import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StockBadge, stockStatus } from "@/components/inventory/StockBadge";

const inventoryMocks = vi.hoisted(() => ({
  pathname: "/backoffice/inventory/products",
  listProducts: vi.fn(),
  getProduct: vi.fn(),
  createInboundOrder: vi.fn(),
  createOutboundOrder: vi.fn(),
  listMovements: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => inventoryMocks.pathname,
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/inventory/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/inventory/api")>("@/lib/inventory/api");
  return { ...actual, ...inventoryMocks };
});

import { InboundOrderForm } from "@/components/inventory/InboundOrderForm";
import { InventoryCarrierView } from "@/components/InventoryCarrierView";
import { InventoryHistoryView } from "@/components/inventory/InventoryHistoryView";
import { InventoryPageHeader } from "@/components/inventory/InventoryPageHeader";
import { InventoryProductsView } from "@/components/inventory/InventoryProductsView";
import { OutboundOrderForm } from "@/components/inventory/OutboundOrderForm";

const products = [
  { id: 1, name: "No Stock", sku: "ZERO", client_name: "Client", category: "fashion" as const, warehouse: "LA" as const, current_stock: 0 },
  { id: 2, name: "Low Stock", sku: "LOW", client_name: "Client", category: "electronics" as const, warehouse: "ZGZ" as const, current_stock: 10 },
  { id: 3, name: "Healthy Stock", sku: "GOOD", client_name: "Client", category: "cosmetics" as const, warehouse: "LA" as const, current_stock: 11 },
];

describe("inventory UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    inventoryMocks.pathname = "/backoffice/inventory/products";
    inventoryMocks.listProducts.mockResolvedValue({ items: products, total: 3, limit: 20, offset: 0 });
    inventoryMocks.getProduct.mockImplementation(async (id: number) => products.find((product) => product.id === id));
    inventoryMocks.createInboundOrder.mockResolvedValue({ id: 1 });
    inventoryMocks.createOutboundOrder.mockResolvedValue({ id: 2 });
    inventoryMocks.listMovements.mockResolvedValue({
      items: [{
        id: 9,
        movement_type: "outbound",
        sku_id: 3,
        quantity: 2,
        reference: null,
        exit_type: "dispatch",
        tracking_number: "TRACK-9",
        warehouse: "LA",
        created_at: "2026-07-02T12:00:00Z",
        user_uuid: "user-uuid-123",
        sku: { id: 3, name: "Healthy Stock", sku: "GOOD", client_name: "Client", category: "cosmetics", warehouse: "LA" },
      }],
      total: 1,
      limit: 20,
      offset: 0,
    });
  });

  it("uses the exact stock thresholds", () => {
    expect(stockStatus(0).label).toBe("Out of stock");
    expect(stockStatus(1).label).toBe("Low stock");
    expect(stockStatus(10).label).toBe("Low stock");
    expect(stockStatus(11).label).toBe("Healthy");
    render(<StockBadge stock={0} />);
    const badge = screen.getByText("Out of stock · 0").parentElement;
    expect(badge).toHaveClass("rounded-md", "border-coral/50", "bg-white", "text-coral");
    expect(badge?.querySelector("[aria-hidden='true']")).toHaveClass("bg-coral");
  });

  it("marks the current inventory section inside the segmented navigation", () => {
    inventoryMocks.pathname = "/backoffice/inventory/orders/outbound";
    render(
      <InventoryPageHeader
        eyebrow="Inventory movement"
        title="Dispatch or record loss"
        description="Test description"
      />,
    );

    const activeLink = screen.getByRole("link", { name: "Dispatch or loss" });
    expect(activeLink).toHaveAttribute("aria-current", "page");
    expect(activeLink).toHaveClass("bg-navy", "text-white");
    expect(screen.getByRole("link", { name: "Products" })).not.toHaveAttribute("aria-current");
  });

  it("renders product name, SKU, warehouse, indicators, and movement links", async () => {
    render(<InventoryProductsView />);
    expect(await screen.findByText("Healthy Stock")).toBeInTheDocument();
    expect(screen.getByText("GOOD")).toBeInTheDocument();
    expect(screen.getAllByText("LA").length).toBeGreaterThan(0);
    expect(screen.getByText("Healthy · 11")).toBeInTheDocument();
    const receiveLinks = screen.getAllByRole("link", { name: "Receive" });
    const dispatchLinks = screen.getAllByRole("link", { name: "Dispatch / loss" });
    expect(receiveLinks[0]).toHaveAttribute("href", "/backoffice/inventory/orders/inbound?product=1");
    expect(receiveLinks[0]).toHaveClass("border-teal/50", "bg-teal/10");
    expect(receiveLinks[0].querySelector("svg")).toBeInTheDocument();
    expect(dispatchLinks[0]).toHaveAttribute("href", "/backoffice/inventory/orders/outbound?product=1");
    expect(dispatchLinks[0]).toHaveClass("border-coral/45", "bg-coral/10");
    expect(dispatchLinks[0].querySelector("svg")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Remove" })).not.toBeInTheDocument();
  });

  it("derives inbound SKU and warehouse and resets entered fields after success", async () => {
    const user = userEvent.setup();
    render(<InboundOrderForm />);
    await screen.findByRole("option", { name: "Healthy Stock · GOOD · LA" });
    await user.selectOptions(screen.getByLabelText("Product"), "3");
    await user.type(screen.getByLabelText("Receipt reference"), " PO-99 ");
    await user.type(screen.getByLabelText("Quantity"), "5");
    await user.click(screen.getByRole("button", { name: "Record receipt" }));

    await waitFor(() => expect(inventoryMocks.createInboundOrder).toHaveBeenCalledWith({
      sku_id: 3,
      quantity: 5,
      reference: "PO-99",
      warehouse: "LA",
    }));
    expect(screen.getByLabelText("Receipt reference")).toHaveValue("");
    expect(screen.getByLabelText("Quantity")).toHaveValue(null);
    expect(screen.getByRole("status")).toHaveTextContent("Received stock");
  });

  it("reactively fetches stock, blocks overstock, and submits loss without tracking", async () => {
    const user = userEvent.setup();
    render(<OutboundOrderForm />);
    await screen.findByRole("option", { name: "Low Stock · LOW · ZGZ" });
    await user.selectOptions(screen.getByLabelText("Product"), "2");
    expect(await screen.findByText("Low stock · 10")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Quantity"), "11");
    expect(screen.getByText("Requested quantity exceeds displayed stock.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record movement" })).toBeDisabled();

    await user.clear(screen.getByLabelText("Quantity"));
    await user.type(screen.getByLabelText("Quantity"), "2");
    await user.selectOptions(screen.getByLabelText("Movement type"), "loss");
    expect(screen.queryByLabelText("Tracking number")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Record movement" }));
    await waitFor(() => expect(inventoryMocks.createOutboundOrder).toHaveBeenCalledWith({
      sku_id: 2,
      quantity: 2,
      exit_type: "loss",
      tracking_number: null,
      warehouse: "ZGZ",
    }));
  });

  it("shows Central API insufficient-stock errors inline beside quantity", async () => {
    inventoryMocks.createOutboundOrder.mockRejectedValue({
      status: 400,
      message: "Insufficient stock for SKU 'GOOD'. Available: 11, requested: 12.",
      fieldErrors: {},
    });
    const user = userEvent.setup();
    render(<OutboundOrderForm />);
    await screen.findByRole("option", { name: "Healthy Stock · GOOD · LA" });
    await user.selectOptions(screen.getByLabelText("Product"), "3");
    await user.type(screen.getByLabelText("Quantity"), "5");
    await user.type(screen.getByLabelText("Tracking number"), "TRACK");
    await user.click(screen.getByRole("button", { name: "Record movement" }));
    expect(await screen.findByText(/Insufficient stock for SKU/)).toBeInTheDocument();
  });

  it("renders movement history including raw user UUID", async () => {
    render(<InventoryHistoryView />);
    expect(await screen.findByText("Dispatch")).toBeInTheDocument();
    expect(screen.getByText("TRACK-9")).toBeInTheDocument();
    expect(screen.getByText("user-uuid-123")).toBeInTheDocument();
  });

  it("does not render the obsolete Engagement 2 utilities tag", () => {
    render(<InventoryCarrierView />);
    expect(screen.queryByText("Engagement 2 utilities live")).not.toBeInTheDocument();
  });
});
