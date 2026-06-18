export type Country = "USA" | "Spain";
export type Currency = "USD" | "EUR";
export type Status = "active" | "suspended";

export type SupplierCategory =
  | "carrier_last_mile"
  | "carrier_international"
  | "warehouse_supplies"
  | "packaging_materials"
  | "reverse_logistics"
  | "fleet_maintenance"
  | "it_and_wms_software"
  | "cleaning_and_facilities";

export interface Supplier {
  id: string;
  name: string;
  country: Country;
  categories: SupplierCategory[];
  rate_per_shipment: number;
  currency: Currency;
  rate_updated_at: string;
  status: Status;
  service_zone: string | null;
  notes: string | null;
  has_contact_email: boolean;
}

export interface SupplierContact {
  id: string;
  contact_email: string | null;
}

export interface SupplierCreate {
  name: string;
  country: Country;
  categories: SupplierCategory[];
  rate_per_shipment: number;
  currency: Currency;
  status: Status;
  service_zone?: string | null;
  contact_email?: string | null;
  notes?: string | null;
}

export interface RateUpdate {
  rate_per_shipment: number;
}

export interface StatusUpdate {
  status: Status;
}

export interface APIError {
  message: string;
  field_errors?: Record<string, string>;
}
