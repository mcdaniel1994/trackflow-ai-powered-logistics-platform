import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentRunDetail, AgentRunSummary } from "@/lib/agents/types";

const agentMocks = vi.hoisted(() => ({ getAgentRuns: vi.fn(), getAgentRun: vi.fn() }));
vi.mock("@/lib/agents/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/agents/api")>("@/lib/agents/api");
  return { ...actual, getAgentRuns: agentMocks.getAgentRuns, getAgentRun: agentMocks.getAgentRun };
});

import { AgentOSDashboard } from "@/components/agents/AgentOSDashboard";

const baseRun: AgentRunSummary = {
  trace_id: "trace-ok",
  agent_name: "trackflow-cx-agent",
  status: "ok",
  route_taken: "both",
  duration_ms: 148,
  total_tokens: 120,
  total_cost_usd: 0.000027,
  guardrail_trigger_count: 0,
  started_at: "2026-08-03T12:00:00Z",
  created_at: "2026-08-03T12:00:00Z",
};

function detail(updates: Partial<AgentRunDetail> = {}): AgentRunDetail {
  return {
    ...baseRun,
    input_summary: null,
    output_summary: "The redacted final answer preview.",
    node_steps: [
      { node_name: "guardrail_input", sequence: 1, status: "ok", duration_ms: 2, tokens: null, cost_usd: null, notes: "outcome=allowed" },
      { node_name: "route", sequence: 2, status: "ok", duration_ms: 24, tokens: 120, cost_usd: 0.000027, notes: "route=both" },
      { node_name: "a_very_long_tool_node_name_that_must_wrap_without_overflow", sequence: 3, status: "error", duration_ms: 122, tokens: null, cost_usd: null, notes: "safe_error_type_that_is_also_intentionally_long" },
    ],
    tool_calls: [{ tool_name: "ticket_status", status: "timeout", duration_ms: 5000, error_type: "timeout", output_summary: null }],
    ...updates,
  };
}

describe("Agent OS dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    agentMocks.getAgentRuns.mockResolvedValue([baseRun]);
    agentMocks.getAgentRun.mockResolvedValue(detail());
  });

  it("renders the exact ordered path, safe metrics, tools, and final-output summary", async () => {
    render(<AgentOSDashboard />);

    expect(await screen.findByText("The redacted final answer preview.")).toBeInTheDocument();
    const path = screen.getByRole("list", { name: "Executed graph path" });
    const steps = within(path).getAllByRole("listitem");
    expect(steps.map((step) => step.textContent)).toEqual([
      expect.stringContaining("guardrail input"),
      expect.stringContaining("route"),
      expect.stringContaining("a very long tool node name"),
    ]);
    expect(screen.getByText("ticket status")).toBeInTheDocument();
    expect(screen.getAllByText("$0.000027")).toHaveLength(2);
    expect(screen.queryByText(/input_summary/i)).not.toBeInTheDocument();
  });

  it("keeps the selected run when auto-refreshed data still contains it", async () => {
    const second = { ...baseRun, trace_id: "trace-rejected", status: "rejected" as const, guardrail_trigger_count: 2 };
    agentMocks.getAgentRuns.mockResolvedValue([baseRun, second]);
    agentMocks.getAgentRun.mockImplementation((traceId: string) =>
      Promise.resolve(detail({ ...second, trace_id: traceId, output_summary: null })),
    );
    render(<AgentOSDashboard />);
    const options = within(await screen.findByRole("listbox", { name: "Recent agent runs" })).getAllByRole("option");
    await userEvent.click(options[1]);
    await waitFor(() => expect(agentMocks.getAgentRun).toHaveBeenCalledWith("trace-rejected"));
    expect(await screen.findByText("2 guardrail triggers")).toBeInTheDocument();
    expect(screen.getByText("Content preview is disabled or unavailable for this run.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(options[1]).toHaveAttribute("aria-selected", "true");
  });

  it("passes agent and status filters through the API contract", async () => {
    render(<AgentOSDashboard />);
    await screen.findByRole("listbox", { name: "Recent agent runs" });
    await userEvent.selectOptions(screen.getByLabelText("Filter by agent"), "trackflow-cx-agent");
    await userEvent.selectOptions(screen.getByLabelText("Filter by status"), "error");
    await waitFor(() => expect(agentMocks.getAgentRuns).toHaveBeenLastCalledWith({ agent: "trackflow-cx-agent", status: "error" }));
  });

  it("shows loading, empty, list failure, and safe missing-detail states", async () => {
    const pending = new Promise<AgentRunSummary[]>(() => undefined);
    agentMocks.getAgentRuns.mockReset();
    agentMocks.getAgentRuns.mockReturnValue(pending);
    const loadingView = render(<AgentOSDashboard />);
    expect(screen.getByRole("status", { name: "Loading agent runs" })).toBeInTheDocument();
    loadingView.unmount();

    agentMocks.getAgentRuns.mockReset();
    agentMocks.getAgentRuns.mockResolvedValue([]);
    const emptyView = render(<AgentOSDashboard />);
    expect(await screen.findByText("No runs found")).toBeInTheDocument();
    emptyView.unmount();

    agentMocks.getAgentRuns.mockReset();
    agentMocks.getAgentRuns.mockRejectedValue({ status: 503, message: "Agent observability is temporarily unavailable." });
    const errorView = render(<AgentOSDashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("temporarily unavailable");
    errorView.unmount();

    agentMocks.getAgentRuns.mockReset();
    agentMocks.getAgentRuns.mockResolvedValue([baseRun]);
    agentMocks.getAgentRun.mockRejectedValueOnce({ status: 404, message: "This agent run is no longer available." });
    render(<AgentOSDashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("no longer available");
  });
});
