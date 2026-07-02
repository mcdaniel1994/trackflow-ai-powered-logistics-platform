import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const incidentMocks = vi.hoisted(() => ({
  createIncident: vi.fn(),
  listIncidents: vi.fn(),
  getIncidentSummary: vi.fn(),
  updateIncidentStatus: vi.fn(),
}));

vi.mock("@/lib/incident-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/incident-api")>("@/lib/incident-api");
  return { ...actual, ...incidentMocks };
});

import { IncidentManagerView } from "@/components/incidents/IncidentManagerView";

const incident = {
  id: 1,
  title: "Carrier missed delivery window",
  description: "The carrier missed the delivery window.",
  category: "carrier_issue" as const,
  status: "open" as const,
  origin: "branch" as const,
  branch: "la_office" as const,
  created_at: "2026-07-02T12:00:00Z",
  updated_at: "2026-07-02T12:00:00Z",
  created_by_user_uuid: "user-1",
};

const emptySummary = {
  total: 0,
  by_status: { open: 0, in_progress: 0, resolved: 0, discarded: 0 },
  by_category: {
    lost_parcel: 0,
    delivery_failure: 0,
    inventory_discrepancy: 0,
    carrier_issue: 0,
    returns_issue: 0,
    warehouse_incident: 0,
    system_failure: 0,
    client_complaint: 0,
    other: 0,
  },
  by_origin: { customer: 0, branch: 0, internal: 0 },
  by_branch: { central: 0, la_warehouse: 0, la_office: 0, zaragoza_warehouse: 0, zaragoza_office: 0 },
};

describe("incident manager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    incidentMocks.listIncidents.mockResolvedValue({ items: [incident], total: 1, limit: 50, offset: 0 });
    incidentMocks.getIncidentSummary.mockResolvedValue({
      ...emptySummary,
      total: 1,
      by_status: { ...emptySummary.by_status, open: 1 },
      by_category: { ...emptySummary.by_category, carrier_issue: 1 },
      by_origin: { ...emptySummary.by_origin, branch: 1 },
      by_branch: { ...emptySummary.by_branch, la_office: 1 },
    });
    incidentMocks.createIncident.mockResolvedValue(incident);
    incidentMocks.updateIncidentStatus.mockResolvedValue({ ...incident, status: "in_progress" });
  });

  it("renders summaries, exact branch labels, clearly labeled filters, and incident data", async () => {
    render(<IncidentManagerView />);
    expect(await screen.findByText("Carrier missed delivery window")).toBeInTheDocument();
    expect(screen.getAllByText("Los Angeles — Office").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Filter by category")).toBeInTheDocument();
    expect(screen.getByText("Filter existing incidents")).toBeInTheDocument();
    expect(screen.getByText(/do not create or edit incidents/i)).toBeInTheDocument();
  });

  it("validates required fields before creating", async () => {
    const user = userEvent.setup();
    render(<IncidentManagerView />);
    await screen.findByText("Carrier missed delivery window");
    await user.click(screen.getByRole("button", { name: "Register incident" }));

    expect(screen.getByText("Title is required.")).toBeInTheDocument();
    expect(screen.getByText("Enter at least five characters.")).toBeInTheDocument();
    expect(incidentMocks.createIncident).not.toHaveBeenCalled();
  });

  it("clears the form and refreshes data after successful creation", async () => {
    const user = userEvent.setup();
    render(<IncidentManagerView />);
    await screen.findByText("Carrier missed delivery window");
    await user.type(screen.getByLabelText("Title"), "Lost parcel report");
    await user.type(screen.getByLabelText("Description"), "Parcel was not delivered.");
    await user.click(screen.getByRole("button", { name: "Register incident" }));

    await waitFor(() => expect(incidentMocks.createIncident).toHaveBeenCalled());
    expect(screen.getByText("Incident registered successfully.")).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("");
    expect(incidentMocks.listIncidents).toHaveBeenCalledTimes(2);
  });

  it("rolls an optimistic status update back when the API fails", async () => {
    incidentMocks.updateIncidentStatus.mockRejectedValue(new Error("technical failure"));
    const user = userEvent.setup();
    render(<IncidentManagerView />);
    await screen.findByText("Carrier missed delivery window");
    await user.selectOptions(screen.getByLabelText("Advance status"), "in_progress");

    await waitFor(() => expect(screen.getAllByText("Open").length).toBeGreaterThan(0));
    expect(screen.getByText("The incident service could not complete the request. Please try again.")).toBeInTheDocument();
  });

  it("shows an informative empty state", async () => {
    incidentMocks.listIncidents.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    render(<IncidentManagerView />);
    expect(await screen.findByText("No incidents match these filters.")).toBeInTheDocument();
  });
});
