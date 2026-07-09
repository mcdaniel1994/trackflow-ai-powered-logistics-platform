export type TelemetryPeriod = { from: string; to: string };

export type DispatchMetricRow = {
  date: string;
  warehouse: string;
  dispatched: number; // exact — from stock_exits
  rejected: number; // best-effort diagnostic — from telemetry_events
  indicative_failure_rate: number; // diagnostic only; may undercount
};

export type WarehouseCountRow = {
  date: string;
  warehouse: string;
  count: number;
};

export type StockLossRow = {
  date: string;
  warehouse: string;
  count: number;
  units: number;
};

export type AccessDenialRow = {
  date: string;
  reason: string;
  count: number;
};

export type DispatchMetrics = { period: TelemetryPeriod; rows: DispatchMetricRow[] };
export type ReceivingMetrics = { period: TelemetryPeriod; rows: WarehouseCountRow[] };
export type StockLossMetrics = { period: TelemetryPeriod; rows: StockLossRow[] };
export type AccessDenialMetrics = { period: TelemetryPeriod; rows: AccessDenialRow[] };

export type TelemetryAPIError = { message: string; status: number };

export type DateRange = { from: string; to: string };
