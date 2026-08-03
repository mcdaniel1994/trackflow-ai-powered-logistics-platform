export type AgentRunStatus = "ok" | "rejected" | "error";

export interface AgentRunSummary {
  trace_id: string;
  agent_name: string;
  status: AgentRunStatus;
  route_taken: string | null;
  duration_ms: number | null;
  total_tokens: number | null;
  total_cost_usd: number | null;
  guardrail_trigger_count: number;
  started_at: string;
  created_at: string;
}

export interface AgentNodeStep {
  node_name: string;
  sequence: number;
  status: string;
  duration_ms: number | null;
  tokens: number | null;
  cost_usd: number | null;
  notes: string | null;
}

export interface AgentToolCall {
  tool_name: string;
  status: string;
  duration_ms: number | null;
  error_type: string | null;
  output_summary: string | null;
}

export interface AgentRunDetail extends AgentRunSummary {
  input_summary: string | null;
  output_summary: string | null;
  node_steps: AgentNodeStep[];
  tool_calls: AgentToolCall[];
}

export interface AgentAPIError {
  message: string;
  status: number;
}
