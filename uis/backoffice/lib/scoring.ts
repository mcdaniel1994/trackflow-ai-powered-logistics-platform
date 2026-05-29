import {
  calculateAverageShipmentDistance,
  calculateShippingCost,
  calculateTotalInventoryValue,
  countProductsByCategory,
  filterProductsByWarehouse,
  filterLowStockProducts,
  groupShipmentsByStatus,
  scoreCarrierForShipment,
  selectBestCarrier,
  sortProductsByStock,
  sortCarriersByReliability,
  validateCarrier,
  validateProduct,
  validateShipment,
  type Carrier,
  type Product,
  type ProductCategory,
  type Shipment,
  type ShipmentStatus,
  type ValidationResult,
  type WarehouseLocation,
} from "@repo/shared-types";
import { carriers, products, shipments } from "@/content/seed";

const WAREHOUSES: WarehouseLocation[] = ["Los Angeles", "Zaragoza"];
const SHIPMENT_STATUSES: ShipmentStatus[] = ["Pending", "Assigned", "In transit", "Delivered", "Failed"];

export interface CarrierQuoteViewModel {
  carrierId: string;
  carrierName: string;
  score: number;
  cost: number;
  isBest: boolean;
  reliability: number;
  deliveryDays: number;
  supportsDestination: boolean;
  supportsPriority: boolean;
  weightFits: boolean;
  fragileReady: boolean;
  totalWeightKg: number;
  maxWeightKg: number;
}

export interface ShipmentScoreViewModel {
  shipmentId: string;
  sku: string;
  productName: string;
  route: string;
  priority: Shipment["priority"];
  quantity: number;
  bestCarrierName: string;
  bestCarrierScore: number;
  bestCarrierCost: number;
  quotes: CarrierQuoteViewModel[];
}

export interface OperationsSummaryViewModel {
  totalInventoryValue: number;
  lowStockCount: number;
  pendingShipmentCount: number;
  topReliabilityCarrier: string;
  scoredShipments: number;
  averageShipmentDistanceKm: number;
  categoryCounts: Array<{ category: ProductCategory; count: number }>;
  warehouseSummaries: Array<{
    warehouse: WarehouseLocation;
    skuCount: number;
    stockUnits: number;
    inventoryValue: number;
  }>;
  shipmentStatusCounts: Array<{ status: ShipmentStatus; count: number }>;
}

export interface InventoryRiskViewModel {
  sku: string;
  name: string;
  category: ProductCategory;
  warehouse: WarehouseLocation;
  stockQuantity: number;
  minStockThreshold: number;
  status: Product["status"];
  inventoryValue: number;
  isFragile: boolean;
}

export interface ValidationHealthViewModel {
  label: string;
  total: number;
  valid: number;
  invalid: number;
  status: "Healthy" | "Needs review";
  errors: string[];
}

function findProductForShipment(shipment: Shipment, allProducts: Product[]): Product {
  const product = allProducts.find((candidate) => candidate.sku === shipment.sku);
  if (!product) {
    throw new Error(`Missing seeded product for shipment ${shipment.id}`);
  }
  return product;
}

function quoteCarriers(
  shipment: Shipment,
  product: Product,
  allCarriers: Carrier[],
  bestCarrierId: string | null,
): CarrierQuoteViewModel[] {
  const totalWeightKg = product.weightKg * shipment.quantity;

  return allCarriers.map((carrier) => {
    const supportsDestination = carrier.operatesIn.includes(shipment.destination.country);
    const supportsPriority = carrier.acceptsPriority.includes(shipment.priority);
    const weightFits = totalWeightKg <= carrier.maxWeightKg;
    const fragileReady = !product.isFragile || carrier.handlesFragile;

    return {
      carrierId: carrier.id,
      carrierName: carrier.name,
      score: scoreCarrierForShipment(carrier, shipment, product),
      cost: calculateShippingCost(shipment, product, carrier),
      isBest: carrier.id === bestCarrierId,
      reliability: carrier.onTimeRate,
      deliveryDays: carrier.avgDeliveryDays,
      supportsDestination,
      supportsPriority,
      weightFits,
      fragileReady,
      totalWeightKg,
      maxWeightKg: carrier.maxWeightKg,
    };
  });
}

export function buildShipmentScoreRows(): ShipmentScoreViewModel[] {
  return shipments.map((shipment) => {
    const product = findProductForShipment(shipment, products);
    const selected = selectBestCarrier(carriers, shipment, product);
    const bestCarrierId = selected?.carrier.id ?? null;

    return {
      shipmentId: shipment.id,
      sku: shipment.sku,
      productName: product.name,
      route: `${shipment.origin} to ${shipment.destination.city}, ${shipment.destination.country}`,
      priority: shipment.priority,
      quantity: shipment.quantity,
      bestCarrierName: selected?.carrier.name ?? "No suitable carrier",
      bestCarrierScore: selected?.score ?? 0,
      bestCarrierCost: selected?.cost ?? 0,
      quotes: quoteCarriers(shipment, product, carriers, bestCarrierId),
    };
  });
}

export function buildOperationsSummary(): OperationsSummaryViewModel {
  const topReliabilityCarrier = sortCarriersByReliability(carriers, "desc")[0];
  const categoryCounts = countProductsByCategory(products);
  const groupedShipments = groupShipmentsByStatus(shipments);

  return {
    totalInventoryValue: calculateTotalInventoryValue(products),
    lowStockCount: filterLowStockProducts(products).length,
    pendingShipmentCount: groupedShipments.Pending.length,
    topReliabilityCarrier: topReliabilityCarrier?.name ?? "None",
    scoredShipments: shipments.length,
    averageShipmentDistanceKm: calculateAverageShipmentDistance(shipments),
    categoryCounts: Object.entries(categoryCounts)
      .map(([category, count]) => ({ category: category as ProductCategory, count }))
      .filter((item) => item.count > 0),
    warehouseSummaries: WAREHOUSES.map((warehouse) => {
      const warehouseProducts = filterProductsByWarehouse(products, warehouse);

      return {
        warehouse,
        skuCount: warehouseProducts.length,
        stockUnits: warehouseProducts.reduce((sum, product) => sum + product.stockQuantity, 0),
        inventoryValue: calculateTotalInventoryValue(warehouseProducts),
      };
    }),
    shipmentStatusCounts: SHIPMENT_STATUSES.map((status) => ({
      status,
      count: groupedShipments[status].length,
    })).filter((item) => item.count > 0),
  };
}

export function buildInventoryRiskSnapshot(): InventoryRiskViewModel[] {
  return sortProductsByStock(products, "asc").map((product) => ({
    sku: product.sku,
    name: product.name,
    category: product.category,
    warehouse: product.warehouse,
    stockQuantity: product.stockQuantity,
    minStockThreshold: product.minStockThreshold,
    status: product.status,
    inventoryValue: Math.round(product.stockQuantity * product.unitCostUSD * 100) / 100,
    isFragile: product.isFragile,
  }));
}

function summarizeValidation(
  label: string,
  results: Array<{ id: string; result: ValidationResult }>,
): ValidationHealthViewModel {
  const errors = results.flatMap(({ id, result }) =>
    result.errors.map((error) => `${id}: ${error}`),
  );
  const invalid = results.filter(({ result }) => !result.valid).length;

  return {
    label,
    total: results.length,
    valid: results.length - invalid,
    invalid,
    status: invalid === 0 ? "Healthy" : "Needs review",
    errors,
  };
}

export function buildSharedDataHealth(): ValidationHealthViewModel[] {
  return [
    summarizeValidation(
      "Products",
      products.map((product) => ({ id: product.sku, result: validateProduct(product) })),
    ),
    summarizeValidation(
      "Shipments",
      shipments.map((shipment) => ({ id: shipment.id, result: validateShipment(shipment) })),
    ),
    summarizeValidation(
      "Carriers",
      carriers.map((carrier) => ({ id: carrier.id, result: validateCarrier(carrier) })),
    ),
  ];
}
