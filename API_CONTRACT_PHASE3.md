# Phase 3 API Contract — Quote & Orders

Authoritative request/response shapes for the quote and order endpoints.
Backend serializers and frontend Zod schemas both answer to this file.

**The trust rule for these two endpoints:** the client may send `service_id`,
`quantity` and customer contact fields. Nothing else. Any price, discount,
total, currency or status in a request body is ignored — not rejected, ignored —
and the server recomputes from its own catalogue. A request carrying
`"price_paise": 1` must produce an order at the real price.

Money is integer paise. Times are ISO 8601 UTC.

---

## `POST /api/v1/orders/quote`

Advisory pricing preview. Never authoritative: order creation recomputes
everything, and payment creation checks again.

Throttle scope `quote`. `AllowAny`.

### Request

```json
{
  "items": [
    { "service_id": "uuid", "quantity": 1 },
    { "service_id": "uuid", "quantity": 2 }
  ]
}
```

- `quantity` is optional and defaults to `1`; must be 1–10.
- Duplicate `service_id` entries are merged by summing quantity.
- 1–20 distinct services per request.

### Response `200`

```json
{
  "currency": "INR",
  "subtotal_paise": 45000,
  "discount_percent": 10,
  "configured_discount_percent": 10,
  "discount_paise": 4500,
  "payable_paise": 40500,
  "eligible_for_discount": true,
  "distinct_service_count": 2,
  "min_distinct_services": 2,
  "expires_at": "2026-09-21T10:05:00Z",
  "lines": [
    {
      "service_id": "uuid",
      "name": "Hair Cutting",
      "unit_price_paise": 30000,
      "quantity": 1,
      "line_total_paise": 30000,
      "discount_alloc_paise": 3000,
      "net_paid_paise": 27000
    }
  ]
}
```

- `discount_percent` is the rate **actually applied**; it is `0` when the basket
  is not eligible, so the UI can never show a discount that was not given.
- `configured_discount_percent` is the campaign's rate whether or not it
  applied, so the UI can say "add 1 more service to unlock 10% off" without
  implying the discount is already on the total.
- `lines` carries the per-line allocation so the UI can show the same numbers a
  winner refund will later be computed from. Allocation is largest-remainder
  with a deterministic tie-break (`REQUIREMENTS.md` §8.3).
- Invariants, asserted server-side before responding:
  `sum(line_total_paise) == subtotal_paise`,
  `sum(discount_alloc_paise) == discount_paise`,
  `sum(net_paid_paise) == payable_paise`.

### Errors

| Code | HTTP | When |
|---|---|---|
| `validation_failed` | 400 | empty `items`, bad quantity, malformed uuid |
| `service_unavailable_for_order` | 400 | a `service_id` is unknown or inactive |

---

## `POST /api/v1/orders`

Creates the order and snapshots its prices. Does **not** take payment —
that is Phase 5.

Throttle scope `order_create`. `AllowAny`.

### Request

```json
{
  "items": [{ "service_id": "uuid", "quantity": 1 }],
  "customer": {
    "name": "Rahul Sharma",
    "phone": "+919000000000",
    "email": "rahul@example.com"
  }
}
```

- `phone` is required, normalised to E.164 with an assumed `+91` country code
  when given as 10 digits.
- `email` is optional (`REQUIREMENTS.md` §8.4).
- Optional `Idempotency-Key` request header: replaying the same key returns the
  original order instead of creating a second one. Double-submitting a checkout
  form must not produce two orders.

### Response `201`

```json
{
  "id": "uuid",
  "public_order_number": "SL-260921-K3M8",
  "status": "DRAFT",
  "currency": "INR",
  "subtotal_paise": 45000,
  "discount_percent_applied": 10,
  "discount_paise": 4500,
  "total_paise": 40500,
  "created_at": "2026-09-21T10:00:00Z",
  "customer": { "name": "Rahul Sharma", "phone_masked": "******0000" },
  "items": [
    {
      "service_name": "Hair Cutting",
      "unit_price_paise": 30000,
      "quantity": 1,
      "line_total_paise": 30000,
      "discount_alloc_paise": 3000,
      "net_paid_paise": 27000
    }
  ]
}
```

- `id` is the unguessable handle the client passes to Phase 5's payment
  endpoints. It is a UUID, not a sequence.
- `public_order_number` is `SL-YYMMDD-XXXX` with a random suffix. **Deliberately
  not sequential**: a sequential number tells any customer how many orders the
  salon has taken.
- `status` is `DRAFT` at creation. Phase 5 moves it to `PAYMENT_PENDING` when a
  gateway order is created.
- The response echoes the phone **masked**. The full number is never returned.
- `items[].service_name` is the snapshot taken at order time, not a live lookup:
  a later price or name change must not rewrite this order.

### Errors

| Code | HTTP | When |
|---|---|---|
| `validation_failed` | 400 | missing customer, bad phone, bad items |
| `service_unavailable_for_order` | 400 | unknown or inactive service |
| `customer_blocked` | 403 | the customer record is blocked |

---

## `GET /api/v1/orders/{id}`

Lets a client that lost its response recover the order. Requires the full UUID,
which is unguessable. Returns the same body as the create response.

Throttle scope `public_read`.

| Code | HTTP | When |
|---|---|---|
| `not_found` | 404 | no such order |

---

## Order state machine

```
DRAFT ──> PAYMENT_PENDING ──> PAID ──> LUCKY_DECIDED ──> COUPON_ACTIVE ──> REDEEMED
  │              │                          │
  │              └──> PAYMENT_FAILED        └──> REFUND_PENDING ──> REFUNDED
  │                        │                            └────────> REFUND_FAILED
  └──> CANCELLED <─────────┘
```

Phase 3 implements the transition table and enforces it. Only `DRAFT` is
reachable from this phase's endpoints; later phases drive the rest. Any
transition not in the table raises `invalid_order_transition` rather than
silently writing the new status.

---

## What the client may send

| Field | Accepted | Notes |
|---|---|---|
| `items[].service_id` | yes | must resolve to an active service |
| `items[].quantity` | yes | 1–10 |
| `customer.name` | yes | 1–120 chars |
| `customer.phone` | yes | normalised to E.164 |
| `customer.email` | yes | optional |
| **any price field** | **ignored** | server recomputes from the catalogue |
| **any total/discount field** | **ignored** | server recomputes |
| **`status`** | **ignored** | server sets it |
