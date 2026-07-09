# CONTEXT — TrackFlow · Telemetry Phase 2: Frontend Capture

## Your Company

**TrackFlow** is a last-mile delivery and warehouse management company operating in Los Angeles (US) and Zaragoza (Spain). You are part of **TrackFlow Tech**, the internal technology team. The backoffice is used daily by warehouse operatives and coordinators to register receiving orders (inbound stock) and dispatch orders (outbound to customers). Today you instrument that backoffice with the events you designed in Phase 1.

---

## Stub Endpoint — TelemetryEvent Model for TrackFlow

Your Pydantic model must accept the envelope defined in your Phase 1 plan. The `properties` field carries the event-specific payload — its contents vary per event but must follow the allowlist defined in your `event-schemas.json`.

```python
from pydantic import BaseModel
from typing import Any
from datetime import datetime

class TelemetryEvent(BaseModel):
    eventId: str           # UUID generated client-side
    timestamp: datetime    # ISO 8601, moment of capture
    sessionId: str         # Session identifier (opaque)
    userId: str            # TinyDB user UUID (never name or email)
    event_type: str        # entity_action format e.g. "dispatch_order_created"
    schemaVersion: str     # e.g. "1.0"
    service: str           # "backoffice"
    properties: dict[str, Any] = {}
```

---

## Inventory Flow — Where to Instrument

These are the backoffice touchpoints where your `track()` calls should live. The component names are references — adapt to your actual implementation.

| Event | Where to call `track()` | Notes |
|---|---|---|
| `receiving_order_created` | After successful API response in the ReceivingOrder creation form | Include `sku_id`, `quantity`, `warehouse`, `client_id` |
| `dispatch_order_created` | After successful API response in the DispatchOrder creation form | Include `sku_id`, `quantity`, `warehouse`, `destination_country` |
| `dispatch_order_failed` | On API error in the DispatchOrder form (catch block) | Include `error_code`, `sku_id`, `warehouse` — flag if `destination_country` is US (SLA sensitivity) |
| `receiving_order_failed` | On API error in the ReceivingOrder form (catch block) | Include `error_code`, `warehouse` |
| `sku_list_viewed` | On mount of the SKU stock list component | Include `warehouse`, `item_count` |

---

## Authentication Flow — Where to Instrument (Additional Activity)

| Event | Where to call `track()` | Notes |
|---|---|---|
| `user_login_succeeded` | After successful TinyDB auth response | Include `warehouse` if determinable at login — never include email or password |
| `user_login_failed` | On failed auth response (catch block or error state) | Include `reason`: `invalid_credentials`, `session_expired`, or `network_error` — never the entered password or email |
| `session_expired` | When the auth token expiry is detected (middleware or auth hook) | Include `sessionId` of the expired session |

---

## Property Allowlists per Event

Every `track()` call for TrackFlow must include only these properties. Nothing else.

| Event | Allowed properties |
|---|---|
| `receiving_order_created` | `sku_id`, `quantity`, `warehouse`, `client_id` |
| `dispatch_order_created` | `sku_id`, `quantity`, `warehouse`, `destination_country` |
| `dispatch_order_failed` | `error_code`, `sku_id`, `warehouse`, `destination_country` |
| `receiving_order_failed` | `error_code`, `warehouse` |
| `sku_list_viewed` | `warehouse`, `item_count` |
| `user_login_succeeded` | `warehouse` |
| `user_login_failed` | `reason` |
| `session_expired` | *(no additional properties beyond the envelope)* |

---

## Business Constraints for Your Implementation

- **`warehouse` is mandatory** in every inventory event (`los_angeles` / `zaragoza`). Thomas Harry (CEO) requires warehouse-level segmentation in every dashboard view — events without it are useless for operational decisions.
- **`client_id` must be an opaque identifier** — never a brand name. TrackFlow handles inventory for multiple client brands and telemetry events must never expose one client's data in a context visible to another.
- **`dispatch_order_failed` in Los Angeles during peak hours** is your highest-urgency event — it feeds the fulfilment rate KPI and has contractual SLA implications. Make sure the `warehouse` and `destination_country` properties are always present on failure events, even if other properties are missing.
- **`userId` is always the TinyDB UUID** of the operative performing the action — never their name or email.
- **No end-customer data in telemetry:** dispatch events track the operative action, not the recipient. Never include recipient name, address, or phone number in any telemetry property.

---

_TrackFlow Tech — Internal document for 4Geeks Academy AI Engineering Track_