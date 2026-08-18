import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RfpTicketDetail, RfpTicketSummary } from "@/lib/rfp/types";

const mocks = vi.hoisted(() => ({
  getRfpTickets: vi.fn(),
  getRfpTicket: vi.fn(),
  uploadRfp: vi.fn(),
  decideDepartment: vi.fn(),
  useRfpTicketStream: vi.fn(),
}));
vi.mock("@/lib/rfp/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/rfp/api")>("@/lib/rfp/api");
  return {
    ...actual,
    getRfpTickets: mocks.getRfpTickets,
    getRfpTicket: mocks.getRfpTicket,
    uploadRfp: mocks.uploadRfp,
    decideDepartment: mocks.decideDepartment,
  };
});
vi.mock("@/lib/realtime/rfp-stream", () => ({
  useRfpTicketStream: mocks.useRfpTicketStream,
}));

import { RfpDesk } from "@/components/agents/RfpDesk";

const summary: RfpTicketSummary = {
  id: "t1",
  rfp_id: "RFP-ABC",
  status: "drafting",
  client_name: "Luna Cosmetics",
  client_country: "US",
  currency: "USD",
  departments_needed: ["warehouse", "lastmile"],
  created_at: "2026-08-05T10:00:00Z",
  updated_at: "2026-08-05T10:00:00Z",
};

function detail(updates: Partial<RfpTicketDetail> = {}): RfpTicketDetail {
  return {
    ...summary,
    services_requested: ["warehousing", "lastmile"],
    monthly_volume: 5000,
    deadline_days: 20,
    budget_range: null,
    readability_grade: 8.1,
    discard_reason: null,
    sections: [
      {
        department_id: "warehouse",
        approval_status: "pending",
        iteration_count: 0,
        draft_content: "Warehouse draft in USD.",
        key_aspects: { aspects: ["storage capacity"] },
        evaluation_results: null,
        approver: null,
        approved_at: null,
        updated_at: "2026-08-05T10:00:00Z",
      },
    ],
    ...updates,
  };
}

function streamTickets(tickets: RfpTicketSummary[]) {
  mocks.useRfpTicketStream.mockReturnValue({
    tickets,
    loading: false,
    error: null,
    connection: "connected",
    newTicketId: null,
    acknowledgeTicket: vi.fn(),
  });
}

describe("RFP Desk", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getRfpTickets.mockResolvedValue([summary]);
    mocks.getRfpTicket.mockResolvedValue(detail());
    streamTickets([summary]);
  });

  it("lists tickets and shows routed detail with department key aspects", async () => {
    render(<RfpDesk />);
    expect(await screen.findByRole("heading", { name: "RFP Desk" })).toBeInTheDocument();
    const list = await screen.findByRole("listbox", { name: "RFP tickets" });
    expect(within(list).getByText("Luna Cosmetics")).toBeInTheDocument();
    expect(await screen.findByText("storage capacity")).toBeInTheDocument();
    expect(screen.getByText("USD")).toBeInTheDocument();
  });

  it("uploads a PDF through the typed client and notifies the user", async () => {
    mocks.uploadRfp.mockResolvedValue({ ...summary, id: "t2", rfp_id: "RFP-NEW", status: "analyzing" });
    render(<RfpDesk />);
    await screen.findByRole("listbox", { name: "RFP tickets" });

    const input = screen.getByLabelText("Upload RFP PDF");
    const file = new File([new Uint8Array([1, 2, 3])], "rfp.pdf", { type: "application/pdf" });
    await userEvent.upload(input, file);

    await waitFor(() => expect(mocks.uploadRfp).toHaveBeenCalledWith(file));
    expect(await screen.findByText(/Uploaded RFP-NEW/)).toBeInTheDocument();
  });

  it("shows the discard reason for a non-RFP ticket", async () => {
    streamTickets([{ ...summary, status: "discarded" }]);
    mocks.getRfpTicket.mockResolvedValue(detail({ status: "discarded", discard_reason: "vendor pitch", sections: [] }));
    render(<RfpDesk />);
    expect(await screen.findByText(/Discarded: vendor pitch/)).toBeInTheDocument();
  });

  it("surfaces a safe upload error", async () => {
    mocks.uploadRfp.mockRejectedValue({ status: 415, message: "Only PDF documents are accepted." });
    render(<RfpDesk />);
    await screen.findByRole("listbox", { name: "RFP tickets" });

    const input = screen.getByLabelText("Upload RFP PDF");
    await userEvent.upload(input, new File([new Uint8Array([1])], "x.pdf", { type: "application/pdf" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Only PDF documents are accepted.");
  });

  it("shows the empty state when there are no tickets", async () => {
    streamTickets([]);
    render(<RfpDesk />);
    expect(await screen.findByText("No RFPs yet")).toBeInTheDocument();
  });

  it("shows per-department approval controls and submits a decision when awaiting approval", async () => {
    const waiting = { ...summary, status: "waiting_for_approval" as const };
    streamTickets([waiting]);
    mocks.getRfpTicket.mockResolvedValue(detail({ status: "waiting_for_approval" }));
    mocks.decideDepartment.mockResolvedValue(detail({ status: "done" }));
    render(<RfpDesk />);

    const approve = await screen.findByRole("button", { name: "Approve" });
    await userEvent.click(approve);

    await waitFor(() => expect(mocks.decideDepartment).toHaveBeenCalledWith("t1", "warehouse", "approve"));
  });

  it("shows the completion banner when the proposal is done", async () => {
    streamTickets([{ ...summary, status: "done" }]);
    mocks.getRfpTicket.mockResolvedValue(detail({ status: "done" }));
    render(<RfpDesk />);
    expect(await screen.findByText(/Proposal complete/)).toBeInTheDocument();
  });
});
