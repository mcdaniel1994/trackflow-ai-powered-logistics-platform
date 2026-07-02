export type Warehouse = "LA" | "ZGZ";
export type Category = "fashion" | "electronics" | "cosmetics";
export type ExitType = "dispatch" | "loss";
export type MovementType = "inbound" | "outbound";

export interface InventoryProduct {
  id: number;
  name: string;
  sku: string;
  client_name: string;
  category: Category;
  warehouse: Warehouse;
  current_stock: number;
}

export type ProductSummary = Omit<InventoryProduct, "current_stock">;

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface InboundOrderInput {
  sku_id: number;
  quantity: number;
  reference: string;
  warehouse: Warehouse;
}

export interface OutboundOrderInput {
  sku_id: number;
  quantity: number;
  exit_type: ExitType;
  tracking_number: string | null;
  warehouse: Warehouse;
}

export interface StockMovement {
  id: number;
  movement_type: MovementType;
  sku_id: number;
  quantity: number;
  reference: string | null;
  exit_type: ExitType | null;
  tracking_number: string | null;
  warehouse: Warehouse;
  created_at: string;
  user_uuid: string;
  sku: ProductSummary;
}

export interface InventoryAPIError {
  message: string;
  status: number;
  fieldErrors: Record<string, string>;
}
