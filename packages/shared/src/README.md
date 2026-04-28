# `src/`

Source code for TrackFlow's shared inventory and carrier management utilities.

## Structure

- **`types/`** — Domain type definitions (Product, Shipment, Carrier, InventoryMovement)
- **`utils/`** — Reusable utility functions for collections, search, transformations, and validation

## Exports

All utilities and types are re-exported via `src/utils/index.ts` for convenient import.

```typescript
import {
  Product,
  Shipment,
  Carrier,
  filterProductsByWarehouse,
  selectBestCarrier,
  validateProduct,
} from '@repo/shared-types';
```

## Building

Run `npm run build` from `packages/shared/` to compile TypeScript to `dist/`.
