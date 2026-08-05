export type RfpTicketStatus =
  | "analyzing"
  | "waiting_for_approval"
  | "drafting"
  | "under_evaluation"
  | "done"
  | "discarded";

export interface RfpDepartmentSection {
  department_id: string;
  approval_status: string;
  iteration_count: number;
  key_aspects: Record<string, unknown> | null;
  evaluation_results: Record<string, unknown> | null;
  approver: string | null;
  approved_at: string | null;
  updated_at: string;
}

export interface RfpTicketSummary {
  id: string;
  rfp_id: string;
  status: RfpTicketStatus;
  client_name: string | null;
  client_country: string | null;
  currency: string | null;
  departments_needed: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface RfpTicketDetail extends RfpTicketSummary {
  services_requested: string[] | null;
  monthly_volume: number | null;
  deadline_days: number | null;
  budget_range: string | null;
  readability_grade: number | null;
  discard_reason: string | null;
  sections: RfpDepartmentSection[];
}

export interface RfpAPIError {
  message: string;
  status: number;
}
