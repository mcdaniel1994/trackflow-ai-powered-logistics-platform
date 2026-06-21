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
import { fetchWithAuth } from "@/lib/auth/client-http";
import type { ServerAPIContext } from "@/lib/server/request-context";

type ThrownAPIError = APIError & {
  status?: number;
};

const API_PATH = "/api/suppliers";

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

async function request<T>(path: string, init?: RequestInit, context?: ServerAPIContext): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (context?.cookieHeader) {
    headers.set("Cookie", context.cookieHeader);
  }

  const url = `${context?.baseUrl ?? ""}${API_PATH}${path}`;
  const requestInit = {
    ...init,
    cache: init?.cache ?? "no-store",
    headers,
  } satisfies RequestInit;

  const response = context
    ? await fetch(url, requestInit)
    : await fetchWithAuth(url, requestInit);

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
  return request<Supplier[]>(query ? `?${query}` : "");
}

export async function getSupplier(id: string, context?: ServerAPIContext): Promise<Supplier> {
  return request<Supplier>(`/${encodeURIComponent(id)}`, undefined, context);
}

export async function getSupplierContact(id: string): Promise<SupplierContact> {
  return request<SupplierContact>(`/${encodeURIComponent(id)}/contact`);
}

export async function createSupplier(body: SupplierCreate): Promise<Supplier> {
  return request<Supplier>("", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function patchSupplierRate(id: string, body: RateUpdate): Promise<Supplier> {
  return request<Supplier>(`/${encodeURIComponent(id)}/rate`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function patchSupplierStatus(id: string, body: StatusUpdate): Promise<Supplier> {
  return request<Supplier>(`/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteSupplier(id: string): Promise<void> {
  await request<void>(`/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
