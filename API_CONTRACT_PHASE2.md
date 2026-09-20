# Phase 2 API Contract

Authoritative response shapes for the Phase 2 public read endpoints. Backend
serializers and frontend Zod schemas must both match this exactly.

All endpoints are:
- `AllowAny`, unauthenticated, read-only (`GET`)
- throttle scope `public_read`
- cached in Redis with explicit invalidation on the corresponding admin write
- never paginated (these lists are small and the site renders them whole)

Money is always integer paise. Times are `HH:MM` strings in the salon timezone.
`null` is used for "absent", never `""` for structured fields.

---

## `GET /api/v1/salon`

```json
{
  "name": "Upendra Salon",
  "slug": "upendra-salon",
  "timezone": "Asia/Kolkata",
  "currency": "INR",
  "address": "12 MG Road, Indore",
  "phone": "+919000000000",
  "whatsapp": "+919000000000",
  "email": "hello@example.com",
  "maps_url": "https://maps.google.com/...",
  "business_hours": [
    {
      "day_of_week": 0,
      "day_name": "Monday",
      "open_time": "10:00",
      "close_time": "21:00",
      "is_closed": false
    }
  ],
  "content": {
    "hero_eyebrow": "Premium grooming. Daily rewards.",
    "hero_heading": "Har Din 5 Lucky Slots",
    "hero_subheading": "Hair Cutting + Shaving + Face Massage free for the day's lucky slots.",
    "why_choose_us": [
      { "title": "Trained stylists", "body": "..." }
    ],
    "social_links": {
      "instagram": "https://...",
      "facebook": null
    }
  }
}
```

- `business_hours` always has 7 entries, ordered Monday(0) → Sunday(6).
- `open_time` / `close_time` are `null` when `is_closed` is true.
- `content` is assembled from `SiteContent` key/value rows. Missing keys fall
  back to a documented default rather than being omitted.

---

## `GET /api/v1/services`

```json
{
  "categories": [
    { "id": "uuid", "name": "Hair", "slug": "hair", "display_order": 1 }
  ],
  "results": [
    {
      "id": "uuid",
      "name": "Hair Cutting",
      "slug": "hair-cutting",
      "description": "Precision cut and styling.",
      "price_paise": 30000,
      "duration_minutes": 30,
      "image_url": "https://.../hair-cutting.webp",
      "is_featured": true,
      "display_order": 1,
      "category": { "id": "uuid", "name": "Hair", "slug": "hair" }
    }
  ]
}
```

- Only `is_active=true` services and categories are returned.
- Ordered by `display_order`, then `name`.
- `category` is `null` for uncategorised services.
- `image_url` is `null` when no image is set.
- **Never** exposes `cost`, internal flags, or price history.

---

## `GET /api/v1/gallery`

```json
{
  "results": [
    {
      "id": "uuid",
      "image_url": "https://.../salon-1.webp",
      "alt_text": "Styling chair at the salon",
      "caption": "Our main floor",
      "display_order": 1,
      "width": 1600,
      "height": 1067
    }
  ]
}
```

`width`/`height` may be `null` if unknown; when present the frontend uses them
to reserve layout space and avoid CLS.

---

## `GET /api/v1/testimonials`

```json
{
  "results": [
    {
      "id": "uuid",
      "author_name": "Rahul S.",
      "rating": 5,
      "body": "Best haircut in town.",
      "display_order": 1
    }
  ]
}
```

Only `is_published=true`. `rating` is an integer 1–5.

---

## `GET /api/v1/faqs`

```json
{
  "results": [
    {
      "id": "uuid",
      "question": "How does the lucky slot work?",
      "answer": "Each day a fixed number of slots ...",
      "display_order": 1
    }
  ]
}
```

Only `is_published=true`.

---

## `GET /api/v1/legal/{slug}`

`slug` ∈ `terms` | `privacy` | `refunds` | `promotion-rules`

```json
{
  "slug": "promotion-rules",
  "title": "Promotion Rules",
  "body_markdown": "## Eligibility\n\n...",
  "version": 3,
  "published_at": "2026-09-20T09:00:00Z"
}
```

Returns the latest **published** version. 404 (`{"error": {"code": "not_found", ...}}`)
when the slug has no published version.

---

## Error envelope

Every error uses the Phase 1 envelope emitted by `common.exceptions`:

```json
{ "error": { "code": "not_found", "message": "Not found.", "request_id": "uuid" } }
```

Frontend branches on `code`, never on `message`.

---

## Caching

| Endpoint | Cache key | Invalidated by |
|---|---|---|
| `/salon` | `public:salon:v1` | Salon, BusinessHour, SiteContent writes |
| `/services` | `public:services:v1` | Service, ServiceCategory writes |
| `/gallery` | `public:gallery:v1` | GalleryImage writes |
| `/testimonials` | `public:testimonials:v1` | Testimonial writes |
| `/faqs` | `public:faqs:v1` | FaqItem writes |
| `/legal/{slug}` | `public:legal:v1:{slug}` | LegalPage publish |

Invalidation is explicit (signal or service-layer call), never TTL-only —
a price change must be visible immediately.
