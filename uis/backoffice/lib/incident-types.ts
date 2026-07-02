export const INCIDENT_CATEGORIES = [
  "lost_parcel",
  "delivery_failure",
  "inventory_discrepancy",
  "carrier_issue",
  "returns_issue",
  "warehouse_incident",
  "system_failure",
  "client_complaint",
  "other",
] as const;

export const INCIDENT_STATUSES = ["open", "in_progress", "resolved", "discarded"] as const;
export const INCIDENT_ORIGINS = ["customer", "branch", "internal"] as const;
export const INCIDENT_BRANCHES = [
  "central",
  "la_warehouse",
  "la_office",
  "zaragoza_warehouse",
  "zaragoza_office",
] as const;

export type IncidentCategory = (typeof INCIDENT_CATEGORIES)[number];
export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];
export type IncidentOrigin = (typeof INCIDENT_ORIGINS)[number];
export type IncidentBranch = (typeof INCIDENT_BRANCHES)[number];

export interface Incident {
  id: number;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: IncidentBranch;
  created_at: string;
  updated_at: string;
  created_by_user_uuid: string | null;
}

export interface IncidentCreate {
  title: string;
  description: string;
  category: IncidentCategory;
  origin: IncidentOrigin;
  branch: IncidentBranch;
}

export interface IncidentPage {
  items: Incident[];
  total: number;
  limit: number;
  offset: number;
}

export interface IncidentSummary {
  total: number;
  by_status: Record<IncidentStatus, number>;
  by_category: Record<IncidentCategory, number>;
  by_origin: Record<IncidentOrigin, number>;
  by_branch: Record<IncidentBranch, number>;
}

export interface IncidentFilters {
  status?: IncidentStatus;
  origin?: IncidentOrigin;
  branch?: IncidentBranch;
  category?: IncidentCategory;
}

export interface IncidentAPIError {
  code: string;
  message: string;
  fields: Record<string, string>;
}

export const CATEGORY_LABELS: Record<IncidentCategory, string> = {
  lost_parcel: "Lost parcel",
  delivery_failure: "Delivery failure",
  inventory_discrepancy: "Inventory discrepancy",
  carrier_issue: "Carrier issue",
  returns_issue: "Returns issue",
  warehouse_incident: "Warehouse incident",
  system_failure: "System failure",
  client_complaint: "Client complaint",
  other: "Other",
};

export const STATUS_LABELS: Record<IncidentStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  discarded: "Discarded",
};

export const ORIGIN_LABELS: Record<IncidentOrigin, string> = {
  customer: "Customer",
  branch: "Branch",
  internal: "Internal",
};

export const BRANCH_LABELS: Record<IncidentBranch, string> = {
  central: "Central",
  la_warehouse: "Los Angeles — Warehouse",
  la_office: "Los Angeles — Office",
  zaragoza_warehouse: "Zaragoza — Warehouse",
  zaragoza_office: "Zaragoza — Office",
};

