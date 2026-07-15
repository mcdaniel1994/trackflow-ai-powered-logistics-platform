import { fetchWithAuth } from "@/lib/auth/client-http";
import type {
  InboundOrderInput,
  InventoryAPIError,
  InventoryClient,
  InventoryProduct,
  OutboundOrderInput,
  Page,
  ProductCreateInput,
  StockMovement,
} from "@/lib/inventory/types";

const API_PATH = "/api/inventory";

function fallbackMessage(status: number) {
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 503) return "Inventory service is temporarily unavailable.";
  if (status === 504) return "Inventory service timed out. Please try again.";
  if (status === 422) return "Please review the highlighted fields.";
  return `Inventory request failed with status ${status}.`;
}

export async function parseInventoryError(response: Response): Promise<InventoryAPIError> {
  const error: InventoryAPIError = {
    message: fallbackMessage(response.status),
    status: response.status,
    fieldErrors: {},
  };

  try {
    const payload = (await response.json()) as Record<string, unknown>;
    if (typeof payload.detail === "string") {
      error.message = payload.detail;
    } else if (Array.isArray(payload.detail)) {
      for (const item of payload.detail) {
        if (!item || typeof item !== "object") continue;
        const detail = item as Record<string, unknown>;
        const location = Array.isArray(detail.loc) ? detail.loc : [];
        const field = String(location.at(-1) ?? "");
        const message = typeof detail.msg === "string" ? detail.msg : error.message;
        if (field && field !== "body") error.fieldErrors[field] = message;
      }
    }
  } catch {
    // The safe status-based fallback prevents HTML or malformed upstream bodies reaching the UI.
  }

  return error;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body) headers.set("Content-Type", "application/json");

  const response = await fetchWithAuth(`${API_PATH}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) throw await parseInventoryError(response);
  return (await response.json()) as T;
}

function pageQuery(limit: number, offset: number) {
  return `?${new URLSearchParams({ limit: String(limit), offset: String(offset) })}`;
}

export function listProducts(limit = 20, offset = 0) {
  return request<Page<InventoryProduct>>(`/products${pageQuery(limit, offset)}`);
}

export function getProduct(id: number) {
  return request<InventoryProduct>(`/products/${id}`);
}

export function listClients() {
  return request<InventoryClient[]>("/clients");
}

export function createClient(displayName: string) {
  return request<InventoryClient>("/clients", {
    method: "POST",
    body: JSON.stringify({ display_name: displayName }),
  });
}

export function renameClient(clientId: string, displayName: string) {
  return request<InventoryClient>(`/clients/${encodeURIComponent(clientId)}`, {
    method: "PATCH",
    body: JSON.stringify({ display_name: displayName }),
  });
}

export function createProduct(input: ProductCreateInput) {
  return request<InventoryProduct>("/products", { method: "POST", body: JSON.stringify(input) });
}

export function updateProductThreshold(productId: number, minStockThreshold: number) {
  return request<InventoryProduct>(`/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify({ min_stock_threshold: minStockThreshold }),
  });
}

export function createInboundOrder(input: InboundOrderInput) {
  return request("/orders/inbound", { method: "POST", body: JSON.stringify(input) });
}

export function createOutboundOrder(input: OutboundOrderInput) {
  return request("/orders/outbound", { method: "POST", body: JSON.stringify(input) });
}

export function listMovements(limit = 20, offset = 0) {
  return request<Page<StockMovement>>(`/orders${pageQuery(limit, offset)}`);
}

export function inventoryError(error: unknown): InventoryAPIError {
  if (error && typeof error === "object" && "message" in error && "status" in error) {
    return error as InventoryAPIError;
  }
  return { message: "Something went wrong. Please try again.", status: 0, fieldErrors: {} };
}
