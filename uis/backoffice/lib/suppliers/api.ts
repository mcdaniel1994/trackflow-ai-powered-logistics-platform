import type {
  APIError,
  Country,
  RateUpdate,
  StatusUpdate,
  Supplier,
  SupplierContact,
  SupplierCategory,
  SupplierCreate,
} from "@/lib/suppliers/types";

type ThrownAPIError = APIError & {
  status?: number;
};

const DEFAULT_API_URL = "http://localhost:8001";
const API_URL = (process.env.NEXT_PUBLIC_SUPPLIER_DIRECTORY_API_URL ?? DEFAULT_API_URL).replace(/\/$/, "");

async function parseAPIError(response: Response): Promise<ThrownAPIError> {
  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    payload = undefined;
  }

  const error: ThrownAPIError = {
    message: `Request failed with status ${response.status}.`,
    status: response.status,
  };

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;

    if (typeof record.detail === "string") {
      error.message = record.detail;
    }

    if (typeof record.message === "string") {
      error.message = record.message;
    }

    if (Array.isArray(record.detail)) {
      const fieldErrors: Record<string, string> = {};
      let firstMessage = "";

      for (const item of record.detail) {
        if (!item || typeof item !== "object") {
          continue;
        }

        const detail = item as Record<string, unknown>;
        const message = typeof detail.msg === "string" ? detail.msg : error.message;
        const loc = Array.isArray(detail.loc) ? detail.loc : [];
        const field = loc.length ? String(loc[loc.length - 1]) : "";

        if (!firstMessage && message) {
          firstMessage = message;
        }

        if (field && field !== "body") {
          fieldErrors[field] = message;
        }
      }

      if (Object.keys(fieldErrors).length) {
        error.field_errors = fieldErrors;
        error.message = "Please review the highlighted fields.";
      } else if (firstMessage) {
        error.message = firstMessage;
      }
    }
  }

  return error;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: init?.cache ?? "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw await parseAPIError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function errorMessage(error: unknown) {
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string") {
      return message;
    }
  }

  return "Something went wrong. Please try again.";
}

export function errorFieldErrors(error: unknown) {
  if (error && typeof error === "object" && "field_errors" in error) {
    const fieldErrors = (error as { field_errors?: unknown }).field_errors;
    if (fieldErrors && typeof fieldErrors === "object") {
      return fieldErrors as Record<string, string>;
    }
  }

  return {};
}

export function isNotFoundError(error: unknown) {
  if (!error || typeof error !== "object") {
    return false;
  }

  const status = (error as ThrownAPIError).status;
  return status === 404 || status === 422;
}

export async function listSuppliers(params: {
  country?: Country;
  category?: SupplierCategory;
}): Promise<Supplier[]> {
  const searchParams = new URLSearchParams();

  if (params.country) {
    searchParams.set("country", params.country);
  }

  if (params.category) {
    searchParams.set("category", params.category);
  }

  const query = searchParams.toString();
  return request<Supplier[]>(query ? `/suppliers?${query}` : "/suppliers");
}

export async function getSupplier(id: string): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${encodeURIComponent(id)}`);
}

export async function getSupplierContact(id: string): Promise<SupplierContact> {
  return request<SupplierContact>(`/suppliers/${encodeURIComponent(id)}/contact`);
}

export async function createSupplier(body: SupplierCreate): Promise<Supplier> {
  return request<Supplier>("/suppliers", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function patchSupplierRate(id: string, body: RateUpdate): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${encodeURIComponent(id)}/rate`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function patchSupplierStatus(id: string, body: StatusUpdate): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteSupplier(id: string): Promise<void> {
  await request<void>(`/suppliers/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
