export interface IncidentInvalidRule {
  code: string;
  field: string;
  label: string;
  count: number;
}

export interface IncidentMetricBreakdown {
  code: string;
  count: number;
  percentage: string;
}

export interface IncidentSatisfactionScore {
  score: number;
  label: string;
  count: number;
}

export interface IncidentSatisfactionSummary {
  closed_incidents: number;
  scored_incidents: number;
  average_score: string;
  scores: IncidentSatisfactionScore[];
}

export interface IncidentValidationError {
  row_number: number;
  field: string;
  code: string;
}

export interface IncidentAnalysisResult {
  total_records: number;
  valid_records: number;
  invalid_records: number;
  invalid_rules: IncidentInvalidRule[];
  categories: IncidentMetricBreakdown[];
  statuses: IncidentMetricBreakdown[];
  countries: IncidentMetricBreakdown[];
  satisfaction: IncidentSatisfactionSummary;
  validation_errors: IncidentValidationError[];
}

