import type { Country, Currency, Status, SupplierCategory } from "@/lib/suppliers/types";

const countryLabels: Record<Country, string> = {
  USA: "United States",
  Spain: "Spain",
};

const countryCurrencies: Record<Country, Currency> = {
  USA: "USD",
  Spain: "EUR",
};

const categoryLabels: Record<SupplierCategory, string> = {
  carrier_last_mile: "Last mile carrier",
  carrier_international: "International carrier",
  warehouse_supplies: "Warehouse supplies",
  packaging_materials: "Packaging materials",
  reverse_logistics: "Reverse logistics",
  fleet_maintenance: "Fleet maintenance",
  it_and_wms_software: "IT and WMS software",
  cleaning_and_facilities: "Cleaning and facilities",
};

const statusLabels: Record<Status, string> = {
  active: "Active",
  suspended: "Suspended",
};

const statusTones: Record<Status, "green" | "coral"> = {
  active: "green",
  suspended: "coral",
};

export const countryOptions = Object.keys(countryLabels) as Country[];
export const categoryOptions = Object.keys(categoryLabels) as SupplierCategory[];
export const statusOptions = Object.keys(statusLabels) as Status[];

export function isCountry(value: string | null | undefined): value is Country {
  return Boolean(value && value in countryLabels);
}

export function isCategory(value: string | null | undefined): value is SupplierCategory {
  return Boolean(value && value in categoryLabels);
}

export function isStatus(value: string | null | undefined): value is Status {
  return Boolean(value && value in statusLabels);
}

export function countryLabel(country: Country) {
  return countryLabels[country];
}

export function categoryLabel(category: SupplierCategory) {
  return categoryLabels[category];
}

export function statusLabel(status: Status) {
  return statusLabels[status];
}

export function statusTone(status: Status) {
  return statusTones[status];
}

export function currencyForCountry(country: Country) {
  return countryCurrencies[country];
}
