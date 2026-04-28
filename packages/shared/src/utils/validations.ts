import { Product, Shipment, Carrier } from '../types/index.js';

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

export function validateProduct(product: Product): ValidationResult {
  const errors: string[] = [];

  if (!product.sku || product.sku.trim() === '') {
    errors.push('SKU must not be empty');
  }

  if (product.weightKg <= 0 || product.weightKg > 100) {
    errors.push('Weight must be greater than 0 and at most 100 kg');
  }

  if (product.dimensions.lengthCm <= 0 || product.dimensions.lengthCm > 200) {
    errors.push('Length must be greater than 0 and at most 200 cm');
  }

  if (product.dimensions.widthCm <= 0 || product.dimensions.widthCm > 200) {
    errors.push('Width must be greater than 0 and at most 200 cm');
  }

  if (product.dimensions.heightCm <= 0 || product.dimensions.heightCm > 200) {
    errors.push('Height must be greater than 0 and at most 200 cm');
  }

  if (product.stockQuantity < 0) {
    errors.push('Stock quantity must be at least 0');
  }

  if (product.minStockThreshold < 0) {
    errors.push('Minimum stock threshold must be at least 0');
  }

  if (product.unitCostUSD <= 0) {
    errors.push('Unit cost must be greater than 0');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

export function validateShipment(shipment: Shipment): ValidationResult {
  const errors: string[] = [];

  if (shipment.quantity <= 0) {
    errors.push('Quantity must be greater than 0');
  }

  if (shipment.declaredValueUSD <= 0) {
    errors.push('Declared value must be greater than 0');
  }

  if (shipment.destination.distanceKm < 0) {
    errors.push('Distance must be at least 0 km');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

export function validateCarrier(carrier: Carrier): ValidationResult {
  const errors: string[] = [];

  if (carrier.baseRateUSD < 0) {
    errors.push('Base rate must be at least 0');
  }

  if (carrier.ratePerKgUSD < 0) {
    errors.push('Rate per kg must be at least 0');
  }

  if (carrier.ratePerKmUSD < 0) {
    errors.push('Rate per km must be at least 0');
  }

  if (carrier.avgDeliveryDays <= 0) {
    errors.push('Average delivery days must be greater than 0');
  }

  if (carrier.onTimeRate < 0 || carrier.onTimeRate > 100) {
    errors.push('On-time rate must be between 0 and 100');
  }

  if (carrier.maxWeightKg <= 0) {
    errors.push('Maximum weight must be greater than 0');
  }

  if (!carrier.operatesIn || carrier.operatesIn.length === 0) {
    errors.push('Carrier must operate in at least 1 country');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}
