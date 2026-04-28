import { Product, Carrier, ProductCategory, WarehouseLocation } from '../types/index.js';

export function filterProductsByWarehouse(
  products: Product[],
  warehouse: WarehouseLocation
): Product[] {
  return products.filter(p => p.warehouse === warehouse);
}

export function filterProductsByCategory(
  products: Product[],
  category: ProductCategory
): Product[] {
  return products.filter(p => p.category === category);
}

export function filterLowStockProducts(products: Product[]): Product[] {
  return products.filter(p => p.stockQuantity <= p.minStockThreshold);
}

export function sortProductsByStock(
  products: Product[],
  order: 'asc' | 'desc'
): Product[] {
  const sorted = [...products];
  sorted.sort((a, b) => {
    const comparison = a.stockQuantity - b.stockQuantity;
    return order === 'asc' ? comparison : -comparison;
  });
  return sorted;
}

export function sortCarriersByReliability(
  carriers: Carrier[],
  order: 'asc' | 'desc'
): Carrier[] {
  const sorted = [...carriers];
  sorted.sort((a, b) => {
    const comparison = a.onTimeRate - b.onTimeRate;
    return order === 'asc' ? comparison : -comparison;
  });
  return sorted;
}
