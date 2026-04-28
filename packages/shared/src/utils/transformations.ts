import { Product, Shipment, Carrier, ProductCategory, ShipmentStatus } from '../types/index.js';

export function calculateShippingCost(
  shipment: Shipment,
  product: Product,
  carrier: Carrier
): number {
  const baseRate = carrier.baseRateUSD;
  const weightCost = product.weightKg * shipment.quantity * carrier.ratePerKgUSD;
  const distanceCost = shipment.destination.distanceKm * carrier.ratePerKmUSD;

  const priorityMultiplier =
    shipment.priority === 'Standard'
      ? 1.0
      : shipment.priority === 'Express'
        ? 1.3
        : 1.6; // Same-day

  const subtotal = (baseRate + weightCost + distanceCost) * priorityMultiplier;
  return Math.round(subtotal * 100) / 100;
}

export function scoreCarrierForShipment(
  carrier: Carrier,
  shipment: Shipment,
  product: Product
): number {
  let score = 0;

  // Operates in destination country: 20 points
  if (carrier.operatesIn.includes(shipment.destination.country)) {
    score += 20;
  }

  // Can handle weight: 20 points
  if (product.weightKg * shipment.quantity <= carrier.maxWeightKg) {
    score += 20;
  }

  // Supports priority: 15 points
  if (carrier.acceptsPriority.includes(shipment.priority)) {
    score += 15;
  }

  // Handles fragile: 15 points (or product not fragile)
  if (!product.isFragile || carrier.handlesFragile) {
    score += 15;
  }

  // Reliability: up to 30 points
  score += carrier.onTimeRate * 0.3;

  return Math.round(score * 100) / 100;
}

export function selectBestCarrier(
  carriers: Carrier[],
  shipment: Shipment,
  product: Product
): { carrier: Carrier; score: number; cost: number } | null {
  const scoredCarriers = carriers
    .map(carrier => ({
      carrier,
      score: scoreCarrierForShipment(carrier, shipment, product),
      cost: calculateShippingCost(shipment, product, carrier),
    }))
    .filter(item => item.score >= 50)
    .sort((a, b) => a.cost - b.cost);

  return scoredCarriers.length > 0 ? scoredCarriers[0] : null;
}

export function countProductsByCategory(
  products: Product[]
): Record<ProductCategory, number> {
  const categories: ProductCategory[] = ['Fashion', 'Electronics', 'Cosmetics', 'Home', 'Other'];
  const counts: Record<ProductCategory, number> = {
    Fashion: 0,
    Electronics: 0,
    Cosmetics: 0,
    Home: 0,
    Other: 0,
  };

  for (const product of products) {
    counts[product.category]++;
  }

  return counts;
}

export function calculateTotalInventoryValue(products: Product[]): number {
  const total = products.reduce((sum, product) => {
    return sum + product.stockQuantity * product.unitCostUSD;
  }, 0);
  return Math.round(total * 100) / 100;
}

export function calculateAverageShipmentDistance(shipments: Shipment[]): number {
  if (shipments.length === 0) {
    return 0;
  }
  const total = shipments.reduce((sum, shipment) => {
    return sum + shipment.destination.distanceKm;
  }, 0);
  return Math.round((total / shipments.length) * 100) / 100;
}

export function groupShipmentsByStatus(
  shipments: Shipment[]
): Record<ShipmentStatus, Shipment[]> {
  const grouped: Record<ShipmentStatus, Shipment[]> = {
    Pending: [],
    Assigned: [],
    'In transit': [],
    Delivered: [],
    Failed: [],
  };

  for (const shipment of shipments) {
    grouped[shipment.status].push(shipment);
  }

  return grouped;
}

export function findTopCarriers(
  shipments: Shipment[],
  topN: number
): Array<{ carrier: string; count: number }> {
  const carrierCounts: Record<string, number> = {};

  for (const shipment of shipments) {
    if (shipment.carrier !== null) {
      carrierCounts[shipment.carrier] = (carrierCounts[shipment.carrier] || 0) + 1;
    }
  }

  return Object.entries(carrierCounts)
    .map(([carrier, count]) => ({ carrier, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, topN);
}
