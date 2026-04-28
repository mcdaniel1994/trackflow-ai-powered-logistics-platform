import { Product, Shipment } from '../types/index.js';

export function findProductBySKU(products: Product[], sku: string): Product | null {
  const lowerSku = sku.toLowerCase();
  for (const product of products) {
    if (product.sku.toLowerCase() === lowerSku) {
      return product;
    }
  }
  return null;
}

export function findShipmentById(shipments: Shipment[], id: string): Shipment | null {
  for (const shipment of shipments) {
    if (shipment.id === id) {
      return shipment;
    }
  }
  return null;
}

export function binarySearchProductByWeight(
  sortedProducts: Product[],
  targetWeight: number
): number {
  let left = 0;
  let right = sortedProducts.length - 1;

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const midWeight = sortedProducts[mid].weightKg;

    if (midWeight === targetWeight) {
      return mid;
    }

    if (midWeight < targetWeight) {
      left = mid + 1;
    } else {
      right = mid - 1;
    }
  }

  return -1;
}
