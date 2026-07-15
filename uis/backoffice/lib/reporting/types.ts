export type ReportWarehouse = "los_angeles" | "zaragoza";

export interface WeeklyPerformanceEntry {
  warehouse: ReportWarehouse;
  client_id: string;
  client_name: string;
  inbound_units_count: number;
  outbound_orders_count: number;
  stockout_events_count: number;
  discrepancy_events_count: number;
  discrepancy_rate: number;
}

export interface WeeklyPerformanceReport {
  week_start: string | null;
  incomplete: boolean;
  entries: WeeklyPerformanceEntry[];
}

export type PipelineStatus = "requested" | "running" | "retryable" | "succeeded" | "failed";
export type PipelineTrigger = "scheduled" | "manual" | "cli";

export interface LatestPipelineRun {
  run_id: string;
  status: PipelineStatus;
  trigger_type: PipelineTrigger;
  requested_by: string;
  scheduled_business_date: string | null;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  attempt: number;
  rows_loaded: number | null;
  error_code: string | null;
}

export interface QueuedPipelineRun {
  run_id: string;
  trigger_type: PipelineTrigger;
  requested_at: string;
}

export interface LatestSuccessfulRun {
  run_id: string;
  finished_at: string;
  target_weeks: string[];
  rows_loaded: number;
}

export interface PipelineRunsStatus {
  latest: LatestPipelineRun | null;
  queued: QueuedPipelineRun[];
  latest_successful: LatestSuccessfulRun | null;
  next_scheduled_refresh: {
    local_time: "07:00";
    timezone: "America/Chicago";
    next_occurrence_utc: string;
  };
}

export interface PipelineRunRequest {
  week_start?: string;
  force_refresh?: boolean;
}

export interface PipelineRunAccepted {
  run_id: string;
  status: "requested";
}

export type ReportingAPIError = {
  message: string;
  status: number;
  code?: string;
};
