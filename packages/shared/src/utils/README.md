# `utils/`

Reusable utility functions for warehouse and carrier management operations.

## Modules

### `collections.ts`
Filter and sort product/carrier collections without mutation.

- `filterProductsByWarehouse(products, warehouse)` — Filter by warehouse location
- `filterProductsByCategory(products, category)` — Filter by product category
- `filterLowStockProducts(products)` — Find products below minimum threshold
- `sortProductsByStock(products, order)` — Sort by stock quantity (asc/desc)
- `sortCarriersByReliability(carriers, order)` — Sort by on-time delivery rate (asc/desc)

### `search.ts`
Linear and binary search utilities.

- `findProductBySKU(products, sku)` — Linear search by SKU (case-insensitive)
- `findShipmentById(shipments, id)` — Linear search by shipment ID
- `binarySearchProductByWeight(sortedProducts, targetWeight)` — Binary search in pre-sorted array

### `transformations.ts`
Carrier selection, cost calculation, and aggregation logic.

**Carrier Scoring & Selection:**
- `calculateShippingCost(shipment, product, carrier)` — Compute total shipping cost with surcharges
- `scoreCarrierForShipment(carrier, shipment, product)` — Score carrier 0–100 based on 5 criteria
- `selectBestCarrier(carriers, shipment, product)` — Find best carrier (score ≥ 50, lowest cost)

**Aggregations & Reports:**
- `countProductsByCategory(products)` — Count products per category
- `calculateTotalInventoryValue(products)` — Sum of all inventory value
- `calculateAverageShipmentDistance(shipments)` — Average delivery distance
- `groupShipmentsByStatus(shipments)` — Organize shipments by status
- `findTopCarriers(shipments, topN)` — Find N most-used carriers

### `validations.ts`
Validate business rules for all entities.

- `validateProduct(product)` — Validate SKU, weight, dimensions, stock, cost
- `validateShipment(shipment)` — Validate quantity, value, distance
- `validateCarrier(carrier)` — Validate rates, reliability, weight capacity, countries

Each function returns `{ valid: boolean, errors: string[] }`.

## Usage

```typescript
import {
  Product,
  filterLowStockProducts,
  selectBestCarrier,
  validateProduct,
} from '@repo/shared-types';

// Find products below minimum stock
const lowStock = filterLowStockProducts(products);

// Validate a product before processing
const result = validateProduct(myProduct);
if (!result.valid) {
  console.error(result.errors);
}

// Select the best carrier for a shipment
const best = selectBestCarrier(carriers, shipment, product);
if (best) {
  console.log(`Selected ${best.carrier.name} at $${best.cost}`);
}
```
