# API Contract — Owner Catalogue (Services & Prices)

The owner panel's **Services & prices** tab. Serializers in
`backend/apps/catalog/views.py`; Zod schemas in `frontend/src/types/owner.ts`.

**Who:** OWNER and MANAGER. The REQUIREMENTS.md section 5 matrix gives price
changes and service management to both. RECEPTIONIST gets 403, and a request
with no session gets 401.

**The money rule:** a price only ever changes through
`apps.catalog.services.change_service_price`. That function locks the row,
writes a `ServicePriceHistory` row (old price, new price, who, why), and
invalidates the public `/services` cache, so the next public read shows the new
price. `Service.save()` refuses any price change that skipped it. Orders
already placed keep their own price snapshots; changing a price never alters
what anyone was charged.

Money is integer paise. Times are ISO 8601 UTC.

---

## `GET /api/v1/owner/services`

Every service, **including hidden ones**, in display order, never cached:

```json
{
  "results": [
    {
      "id": "uuid",
      "name": "Hair Cutting",
      "slug": "hair-cutting",
      "description": "…",
      "category": { "id": "uuid", "name": "Hair" },
      "price_paise": 30000,
      "duration_minutes": 30,
      "is_active": true,
      "is_featured": true,
      "display_order": 1,
      "image_url": null,
      "updated_at": "…",
      "price_history": [
        {
          "old_price_paise": 28000,
          "new_price_paise": 30000,
          "changed_at": "…",
          "changed_by": "owner@example.com",
          "reason": "Festival pricing"
        }
      ]
    }
  ]
}
```

`price_history` is newest first, at most 5 entries. `category` is `null` when
the service has none.

## `POST /api/v1/owner/services/{id}/price`

```json
{ "price_paise": 32050, "reason": "optional, ≤200 chars" }
```

- `price_paise` must be an integer from **100** (₹1) to **50,000,000** (₹5,00,000).
  A float or string gives `400`. The panel converts the owner's rupee input to
  paise digit by digit (`rupeesToPaise`), never through floating point.
- The current price gives `400` ("That is already the price of this
  service."). An edit that changes nothing is reported as an error, not
  silently accepted.
- Writes a `ServicePriceHistory` row and an `AuditLog` row
  (`service.price_changed`, before and after).
- Returns the updated service in the shape above.

## `PATCH /api/v1/owner/services/{id}`

Any subset of:

| Field | Rule |
|---|---|
| `is_active` | `false` hides the service from the public site at once |
| `is_featured` | the "Popular" badge |
| `duration_minutes` | 5–480 |
| `description` | ≤2000 chars |

`price_paise` is **not** accepted here. It is ignored, so a body containing only
a price has nothing to change and returns `400`. That stops a client slipping a
price past the history. Fields whose value is unchanged are dropped, and no
audit row is written for them. Real changes are written as `service.updated`
with before and after values.

Errors: `404` for an unknown service or one belonging to another salon.
