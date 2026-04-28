# `types/`

Domain types and interfaces for TrackFlow's inventory and carrier management system.

## Exported Types

### Product & Inventory

- `Product` — Represents a product stored in TrackFlow's warehouses
  - SKU, name, category, weight, dimensions, warehouse location, stock, cost, fragility, status
- `Dimensions` — Physical dimensions (length, width, height in cm)
- `ProductCategory` — "Fashion" | "Electronics" | "Cosmetics" | "Home" | "Other"
- `WarehouseLocation` — "Los Angeles" | "Zaragoza"
- `ProductStatus` — "Active" | "Low stock" | "Out of stock" | "Discontinued"
- `InventoryMovement` — Tracks inbound/outbound/transfer/adjustment changes
- `MovementType` — "Inbound" | "Outbound" | "Transfer" | "Adjustment"

### Shipment & Delivery

- `Shipment` — Represents a delivery order
  - ID, SKU, quantity, origin, destination, priority, value, assigned carrier, status, created date
- `Destination` — Delivery location (city, country, postal code, distance)
- `Country` — "United States" | "Spain"
- `ShipmentPriority` — "Standard" | "Express" | "Same-day"
- `ShipmentStatus` — "Pending" | "Assigned" | "In transit" | "Delivered" | "Failed"

### Carrier

- `Carrier` — Represents a delivery carrier
  - ID, name, operating countries, base rate, rates per kg/km, delivery days, on-time rate, max weight, fragile handling, accepted priorities
