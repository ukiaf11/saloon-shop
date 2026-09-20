# Salon Lucky Customer Platform — Consolidated Requirements

**Derived from:** `01_PROJECT_BLUEPRINT_AND_ARCHITECTURE.md`, `02_BACKEND_PAYMENT_LUCKY_ENGINE_SECURITY.md`, `03_FRONTEND_ADMIN_DEPLOYMENT_TESTING.md`
**Status:** Greenfield — no code exists yet. This document is the single checklist of *what must be built*.
**Last updated:** 2026-09-20

---

## 0. One-paragraph summary

A mobile-first single-page salon website where a customer picks services, gets an automatic 10% discount for 2+ distinct services, pays via Razorpay (UPI/card), and immediately learns whether they hit one of the day's pre-generated "lucky slots". Winners get a refund of the reward-attributable amount plus a free-service entitlement coupon; everyone gets a QR coupon. A separate role-based admin panel manages services, pricing, the daily campaign, payments, coupons, refunds, reports and audit logs. Every money and promotion decision must be reproducible from persisted data.

---

## 1. Environment & prerequisites (needed before coding)

| Requirement | Detail | Blocking? |
|---|---|---|
| Razorpay account | Test keys for dev, live keys for launch; webhook secret | Blocks Phase 5 |
| Domain + DNS | Production domain, Cloudflare account | Blocks Phase 10 |
| Managed PostgreSQL 15+ | Or self-hosted with backups | Blocks Phase 1 (dev can use Docker) |
| Managed Redis 7+ | Cache, locks, Celery broker | Blocks Phase 1 (dev can use Docker) |
| Object storage | S3/R2/Spaces for service & gallery images | Blocks Phase 2 |
| Secret manager | Vault / AWS KMS / Doppler / platform secrets | Blocks Phase 5 (dev can use env + Fernet) |
| Error monitoring | Sentry DSN | Phase 10 |
| SMS/OTP provider | MSG91 / Twilio / Razorpay-adjacent, for phone OTP | Phase 6 (optional in MVP) |
| Salon content | Logo, service list + prices, photos, address, hours, GST/legal name | Blocks Phase 2 content seed |
| Legal copy | Terms, privacy, refund policy, promotion rules (needs owner sign-off) | Blocks launch |

---

## 2. Database requirements (PostgreSQL)

### 2.1 Global conventions

- **Money:** `BIGINT` paise only. No `FLOAT`/`REAL` anywhere in the money path.
- **IDs:** UUIDv4 primary keys for all externally-referenced entities; internal-only tables may use `BIGSERIAL`.
- **Time:** all `TIMESTAMPTZ`, stored UTC, rendered in `Asia/Kolkata`.
- **Dates:** `campaign_date` is a `DATE` in salon timezone, not derived from UTC at read time.
- **Enums:** Postgres `CHECK` constraints or `VARCHAR` + Django `TextChoices` (prefer the latter for migration ease).
- **Soft delete:** services and content use `is_active` flags; orders/payments/coupons/audit are never deleted.
- **Every table:** `created_at`, and `updated_at` where mutable.

### 2.2 Tables

#### accounts
| Table | Key fields | Notes |
|---|---|---|
| `AdminUser` | `id`, `email` (unique, citext), `password_hash`, `full_name`, `role`, `is_active`, `mfa_enabled`, `mfa_secret_ref`, `last_login_at`, `failed_login_count`, `locked_until` | Roles: `OWNER`, `MANAGER`, `RECEPTIONIST`. Argon2 hashing. |
| `AdminSession` | `id`, `admin_user_id`, `session_key`, `ip`, `user_agent`, `expires_at`, `revoked_at` | Server-side sessions; no long-lived JWT in browser. |
| `MfaRecoveryCode` | `id`, `admin_user_id`, `code_hash`, `used_at` | |
| `LoginAttempt` | `id`, `email`, `ip`, `success`, `created_at` | Feeds throttling + brute-force alert. |

#### salons
| Table | Key fields | Notes |
|---|---|---|
| `Salon` | `id`, `name`, `slug` (unique), `timezone` (default `Asia/Kolkata`), `currency` (`INR`), `address`, `phone`, `email`, `whatsapp`, `maps_url`, `status` | Single row for MVP; FK kept everywhere so multi-branch is additive later. |
| `BusinessHour` | `id`, `salon_id`, `day_of_week` (0–6), `open_time`, `close_time`, `is_closed` | Unique `(salon_id, day_of_week)`. |

#### catalog
| Table | Key fields | Notes |
|---|---|---|
| `Service` | `id`, `salon_id`, `name`, `slug`, `description`, `price_paise`, `duration_minutes`, `image_key`, `is_active`, `is_featured`, `display_order`, `category_id` | Unique `(salon_id, slug)`. Index `(salon_id, is_active, display_order)`. `CHECK price_paise >= 0`. |
| `ServiceCategory` | `id`, `salon_id`, `name`, `slug`, `display_order`, `is_active` | Optional; enables filtering when the list grows. |
| `ServicePriceHistory` | `id`, `service_id`, `old_price_paise`, `new_price_paise`, `changed_by` (FK AdminUser), `changed_at`, `reason` | Written by a DB-level trigger or a service-layer hook — never optional. |

#### customers
| Table | Key fields | Notes |
|---|---|---|
| `Customer` | `id`, `name`, `phone` (unique per salon, E.164), `email`, `phone_verified_at`, `is_blocked`, `blocked_reason` | Index on `phone`. |
| `PhoneOtp` | `id`, `phone`, `code_hash`, `purpose`, `attempts`, `expires_at`, `consumed_at`, `ip` | Never store the plain OTP. Short TTL (5 min). |

#### promotions
| Table | Key fields | Notes |
|---|---|---|
| `CampaignConfig` | `id`, `salon_id`, `daily_capacity`, `lucky_count`, `discount_percent`, `min_distinct_services`, `max_entries_per_phone_per_day`, `reward_type`, `reward_definition` (JSONB), `coupon_validity_days`, `effective_from` (DATE), `created_by`, `created_at` | Append-only versioned config. Read = "latest row with `effective_from <= date`". `CHECK lucky_count <= daily_capacity`, `CHECK discount_percent BETWEEN 0 AND 100`, `CHECK daily_capacity > 0`. |
| `DailyCampaign` | `id`, `salon_id`, `campaign_date`, `config_id`, `capacity`, `lucky_count`, `discount_percent`, `min_distinct_services`, `reward_snapshot` (JSONB), `status`, `seed_commitment` (SHA256 hex), `encrypted_seed_reference`, `encrypted_winning_positions`, `paid_count`, `winner_count`, `created_at`, `closed_at` | **Unique `(salon_id, campaign_date)`.** Status: `SCHEDULED`/`ACTIVE`/`CLOSED`. Row is the concurrency lock target (`SELECT ... FOR UPDATE`). Winning positions are never exposed through any admin serializer. |
| `SlotReservation` | `id`, `daily_campaign_id`, `customer_id`, `order_id`, `reservation_token`, `status`, `expires_at`, `created_at` | Status: `ACTIVE`/`CONSUMED`/`EXPIRED`/`CANCELLED`. Partial index on `(daily_campaign_id)` where `status='ACTIVE'` — this is the hot capacity query. TTL 10 min. |

#### orders
| Table | Key fields | Notes |
|---|---|---|
| `Order` | `id`, `salon_id`, `customer_id`, `daily_campaign_id`, `public_order_number` (unique, human-readable), `subtotal_paise`, `discount_paise`, `total_paise`, `discount_percent_applied`, `status`, `enters_lucky_campaign` (bool), `created_at`, `paid_at`, `idempotency_key` | Status per the order state machine. `CHECK total_paise = subtotal_paise - discount_paise`. Indexes on `(salon_id, created_at)`, `(customer_id)`, `(daily_campaign_id)`. |
| `OrderItem` | `id`, `order_id`, `service_id`, `service_name_snapshot`, `unit_price_paise`, `quantity`, `line_total_paise`, `discount_alloc_paise`, `net_paid_paise` | Snapshot fields are mandatory — price changes must not rewrite history. `discount_alloc_paise` is the proportional discount share computed at order creation via largest-remainder with an `order_item.id` tie-break (§8.3); `net_paid_paise = line_total_paise - discount_alloc_paise` is what a winner refund is measured against (§8.1). Invariants `SUM(discount_alloc_paise) == order.discount_paise` and `SUM(net_paid_paise) == order.total_paise` are asserted at write time. |
| `Quote` | `id`, `service_ids` (JSONB), `subtotal_paise`, `discount_paise`, `payable_paise`, `expires_at` | Optional; can live in Redis instead. Informational only — never authoritative. |

#### payments
| Table | Key fields | Notes |
|---|---|---|
| `Payment` | `id`, `order_id`, `provider`, `gateway_order_id`, `gateway_payment_id` (**unique, nullable**), `amount_paise`, `currency`, `status`, `payment_method`, `verified_at`, `failure_code`, `failure_reason`, `created_at` | Status: `CREATED`/`AUTHORIZED`/`CAPTURED`/`FAILED`/`PARTIALLY_REFUNDED`/`REFUNDED`. |
| `PaymentWebhookEvent` | `id`, `provider`, `gateway_event_id`, `event_type`, `payload_hash`, `encrypted_payload`, `status`, `received_at`, `processed_at`, `error` | **Unique `(provider, gateway_event_id)`** — this constraint *is* the idempotency mechanism. |
| `PaymentGatewayConfig` | `id`, `salon_id`, `provider`, `mode` (`test`/`live`), `key_id_masked`, `secret_reference`, `webhook_secret_reference`, `is_active`, `last_tested_at`, `last_test_status`, `updated_by`, `updated_at` | **Never stores plaintext secrets.** Only references into the secret manager. |

#### coupons
| Table | Key fields | Notes |
|---|---|---|
| `Coupon` | `id`, `order_id` (**unique**), `opaque_token` (unique, ≥128-bit, URL-safe), `coupon_code` (short human code, unique), `status`, `is_lucky_winner`, `valid_from`, `valid_until`, `created_at` | Status: `PENDING`/`ACTIVE`/`EXPIRED`/`CANCELLED`/`REDEEMED`. Index on `opaque_token` and `coupon_code`. |
| `CouponEntitlement` | `id`, `coupon_id`, `service_id`, `service_name_snapshot`, `kind` (`PAID`/`FREE_REWARD`), `quantity`, `consumed` | What the customer may actually claim at the counter. |
| `CouponRedemption` | `id`, `coupon_id` (**unique** — one-time), `redeemed_by` (FK AdminUser), `redeemed_at`, `location`, `notes` | Unique constraint enforces one-time redemption even under a concurrent double scan. |

#### refunds
| Table | Key fields | Notes |
|---|---|---|
| `Refund` | `id`, `payment_id`, `order_id`, `provider_refund_id` (unique, nullable), `amount_paise`, `reason`, `status`, `attempt_count`, `next_attempt_at`, `last_error`, `idempotency_key` (unique), `created_at`, `updated_at` | Status: `NOT_REQUIRED`/`PENDING`/`PROCESSING`/`COMPLETED`/`FAILED`/`RETRYING`/`MANUAL_REVIEW_REQUIRED`. |
| `RefundAttempt` | `id`, `refund_id`, `attempt_number`, `request_hash`, `response_code`, `error`, `created_at` | Full retry trail for audit. |

#### lucky
| Table | Key fields | Notes |
|---|---|---|
| `LuckyDecision` | `id`, `order_id` (**unique**), `daily_campaign_id`, `participant_number`, `is_winner`, `decision_hash`, `created_at` | **Unique `(daily_campaign_id, participant_number)`** and **unique `order_id`** together make double-processing structurally impossible. |

#### content
| Table | Key fields | Notes |
|---|---|---|
| `SiteContent` | `id`, `salon_id`, `key`, `value` (JSONB), `updated_by`, `updated_at` | Key/value for hero heading, subheading, CTA labels, social links. Unique `(salon_id, key)`. |
| `GalleryImage` | `id`, `salon_id`, `image_key`, `alt_text`, `caption`, `display_order`, `is_active` | |
| `Testimonial` | `id`, `salon_id`, `author_name`, `rating`, `body`, `is_published`, `display_order` | |
| `FaqItem` | `id`, `salon_id`, `question`, `answer`, `display_order`, `is_published` | |
| `LegalPage` | `id`, `salon_id`, `slug` (`terms`/`privacy`/`refunds`/`promotion-rules`), `title`, `body_markdown`, `version`, `published_at` | Versioned — promotion rules in force at order time must be recoverable. |

#### audit & ops
| Table | Key fields | Notes |
|---|---|---|
| `AuditLog` | `id`, `actor_id`, `actor_type`, `action`, `entity_type`, `entity_id`, `before_json`, `after_json`, `ip_address`, `user_agent`, `request_id`, `created_at` | Append-only. No UPDATE/DELETE grant for the app DB user. Index `(entity_type, entity_id)` and `(created_at)`. Values masked before write. |
| `ExportJob` | `id`, `requested_by`, `kind`, `filters_json`, `status`, `file_key`, `expires_at`, `created_at` | Report exports run through Celery, not the request cycle. |
| `OutboundNotification` | `id`, `channel`, `recipient_masked`, `template`, `status`, `attempts`, `created_at` | SMS/WhatsApp/email dispatch log. |

### 2.3 Constraints that must exist at the DB level (not only in Python)

```
UNIQUE (salon_id, campaign_date)                  -- DailyCampaign
UNIQUE (provider, gateway_event_id)               -- PaymentWebhookEvent
UNIQUE (gateway_payment_id)                       -- Payment
UNIQUE (order_id)                                 -- LuckyDecision
UNIQUE (daily_campaign_id, participant_number)    -- LuckyDecision
UNIQUE (order_id)                                 -- Coupon
UNIQUE (opaque_token)                             -- Coupon
UNIQUE (coupon_id)                                -- CouponRedemption
UNIQUE (provider_refund_id)                       -- Refund
UNIQUE (idempotency_key)                          -- Refund

CHECK daily_capacity > 0
CHECK lucky_count >= 0 AND lucky_count <= daily_capacity
CHECK discount_percent BETWEEN 0 AND 100
CHECK amount_paise >= 0
CHECK total_paise = subtotal_paise - discount_paise
CHECK participant_number >= 1
```

### 2.4 Migration & data safety

- Additive migrations preferred; destructive migrations need explicit review and a backup checkpoint.
- Migration check runs in CI (`makemigrations --check --dry-run`).
- Daily automated backup + documented, *tested* restore procedure. PITR if budget allows.

---

## 3. Backend requirements (Django + DRF)

### 3.1 App layout

```
backend/
  config/            settings (base/local/staging/prod), urls, celery, asgi/wsgi
  apps/
    accounts/        admin users, roles, MFA, sessions, throttling
    salons/          salon profile, business hours
    catalog/         services, categories, price history
    customers/       customer records, phone OTP
    orders/          quote engine, order creation, order state machine
    payments/        gateway config, payment records, verification, webhooks
    promotions/      campaign config, daily campaign, lucky engine, reservations
    coupons/         coupon issue, entitlement, redemption
    refunds/         refund calculator, refund state machine, retries
    analytics/       dashboard aggregates, reports, exports
    content/         site content, gallery, testimonials, FAQ, legal pages
    audit/           audit log writer, middleware, admin views
  integrations/
    payments/        base.py (abstract gateway), razorpay.py, cashfree.py (stub)
    secrets/         base.py, vault.py / kms.py / env_fernet.py
    sms/             base.py, provider impl
  common/            money utils, idempotency, locking, request_id middleware, exceptions
  tasks/             celery tasks + beat schedule
```

### 3.2 Core domain services (pure functions / service classes, framework-independent, unit-testable)

| Service | Responsibility |
|---|---|
| `QuoteCalculator` | distinct-service count → discount eligibility → subtotal/discount/payable in paise |
| `DiscountAllocator` | distributes order discount across line items (largest-remainder), guarantees exact sum |
| `CapacityGuard` | row-locks `DailyCampaign`, computes `paid_count + active_reservations`, admits or rejects |
| `LuckyEngine` | seed generation, commitment hashing, deterministic winning-position sampling, membership check |
| `ParticipantAssigner` | atomic `paid_count` increment → `participant_number` |
| `CouponIssuer` | opaque token generation, entitlement rows, validity window |
| `RefundCalculator` | reward-attributable-only (§8.1): sums `net_paid_paise` of purchased lines whose service is in the reward package, minus prior refunds → `eligible_refund_paise`; reward services not purchased → `free_service_entitlements` |
| `CouponRedeemer` | `SELECT FOR UPDATE`, state validation, redemption record |
| `CampaignProvisioner` | scheduled + lazy daily campaign creation, idempotent on `(salon, date)` |
| `AuditWriter` | before/after diff, masking, request context |

**Rule:** none of these may import DRF request objects. They take primitives and return primitives.

### 3.3 API surface

**Public**
```
GET   /api/v1/salon                      salon profile, hours, content
GET   /api/v1/services                   active services (+categories)
GET   /api/v1/promotion/today            capacity, paid, remaining, winners found/remaining
POST  /api/v1/otp/request                phone OTP request
POST  /api/v1/otp/verify                 phone OTP verify
POST  /api/v1/orders/quote               server-side pricing preview
POST  /api/v1/orders                     create order + reserve slot
POST  /api/v1/payments/create            create gateway order, return safe checkout config
POST  /api/v1/payments/verify            signature verification + lucky decision + coupon
GET   /api/v1/orders/{id}/status         poll fallback when client verify is interrupted
GET   /api/v1/coupons/{token}            public coupon view (opaque token only)
GET   /api/v1/legal/{slug}               terms / privacy / refunds / promotion-rules
```

**Webhooks**
```
POST  /api/v1/webhooks/razorpay          signature-verified, idempotent, always 200 on duplicate
```

**Admin** (session-cookie auth + CSRF + RBAC)
```
POST   /api/v1/admin/auth/login | logout | mfa/verify | mfa/setup | reauth
GET    /api/v1/admin/dashboard
CRUD   /api/v1/admin/services            + PATCH price (creates history)
CRUD   /api/v1/admin/service-categories
GET    /api/v1/admin/orders              rich filters + pagination
GET    /api/v1/admin/payments
GET    /api/v1/admin/refunds             + POST {id}/retry  (permission-gated)
GET    /api/v1/admin/coupons             + POST {id}/redeem, POST {id}/cancel
POST   /api/v1/admin/coupons/lookup      by code / phone / order / scanned token
GET    /api/v1/admin/customers
GET/PATCH /api/v1/admin/campaign-settings
GET    /api/v1/admin/campaigns           daily history, read-only for closed
GET/PUT  /api/v1/admin/payment-gateway   + POST /test  (MFA re-auth required)
CRUD   /api/v1/admin/content/*           site content, gallery, testimonials, FAQ, legal
GET    /api/v1/admin/reports             + POST /export (async job)
GET    /api/v1/admin/audit-logs
CRUD   /api/v1/admin/users               OWNER only
```

### 3.4 Transactional guarantees (the non-negotiable list)

1. **Quote is advisory.** Order creation and payment creation each recompute totals from the DB.
2. **Capacity:** reservation created only inside a transaction holding `SELECT ... FOR UPDATE` on the `DailyCampaign` row.
3. **Payment amount** always read from `Order.total_paise`, never from the request body.
4. **Webhook idempotency** via unique `(provider, gateway_event_id)` insert-first, then process.
5. **Lucky decision** runs once per order, inside one transaction that also consumes the reservation, increments `paid_count`, assigns `participant_number`, creates `LuckyDecision` and `Coupon`. Loser of the verify-vs-webhook race reads the existing decision and returns it unchanged.
6. **Refunds** are idempotent by `idempotency_key`; no blind re-calls to the provider.
7. **Coupon redemption** is a `SELECT FOR UPDATE` + unique-constraint pair.
8. **Campaign config lock:** once `paid_count >= 1`, today's config is immutable; edits create a new `CampaignConfig` with `effective_from = tomorrow`.
9. **Winning positions never leave the server** — not in any API response, admin serializer, log line, or error message.

### 3.5 Background jobs (Celery + Beat)

| Task | Schedule | Purpose |
|---|---|---|
| `close_and_open_daily_campaign` | 00:00 Asia/Kolkata | close yesterday, create today, generate seed + positions |
| `expire_stale_reservations` | every 2 min | flip expired `ACTIVE` reservations to `EXPIRED` |
| `retry_pending_refunds` | every minute (backoff-aware) | 1m → 5m → 30m → 2h → manual review |
| `reconcile_payments` | every 15 min | fetch provider status for uncertain payments, flag mismatches |
| `process_webhook_event` | on demand | async body of webhook processing |
| `generate_export` | on demand | CSV/Excel report generation → object storage |
| `send_notification` | on demand | SMS/WhatsApp coupon link |
| `expire_coupons` | daily | flip past-validity coupons to `EXPIRED` |

Plus **lazy fallback**: any campaign-dependent request checks for today's campaign and creates it atomically if the scheduler failed.

### 3.6 Security requirements

- HTTPS-only, HSTS, CSP (nonce-based, Razorpay script/frame allowlisted), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`.
- Admin auth: Argon2 password hashing, TOTP MFA (mandatory for OWNER), server-side sessions in `HttpOnly`/`Secure`/`SameSite` cookies, login throttling with account lockout.
- RBAC matrix enforced at the permission-class layer, re-verified in the service layer for sensitive actions.
- Step-up re-auth (MFA challenge) for: gateway config change, secret rotation, owner email change, adding an owner, manual refunds, future lucky-count change.
- Django CSRF enabled for all cookie-authenticated mutations; never globally disabled.
- CORS: explicit origin allowlist, no wildcard on credentialed endpoints.
- Rate limits: quote 30/min/IP, order 10/min/IP, OTP 3/10min/phone + 5/10min/IP, verify 10/min/order, coupon lookup 30/min/IP, admin login 5/15min per account+IP.
- Secrets in a secret manager; DB stores references only. Nothing sensitive in Git.
- Logging bans: gateway secrets, CVV, card numbers, UPI PIN, OTP, raw webhook bodies (hash or encrypt instead).
- Postgres on a private network, least-privilege app user, TLS if remote.

### 3.7 Observability

- `request_id` on every request, propagated into logs, audit records and Sentry scope.
- Structured JSON logs with an event taxonomy (`payment_verified`, `lucky_decided`, `refund_failed`, …).
- Metrics/alerts: API error rate, latency, webhook signature failures, refund failures, missing daily campaign, Celery queue depth, DB/Redis health, admin brute-force.

---

## 4. Frontend requirements (Next.js + TypeScript + Tailwind + Motion)

### 4.1 Public site — one page, these sections in order

Navbar → Hero → Today's Lucky Campaign → Services → Sticky Selection Cart → Discount Reveal → How It Works → Premium Packages → Gallery → Testimonials → Why Choose Us → Opening Hours → Location/Map → FAQ → Policies → Footer, plus a floating WhatsApp button.

Separate routes: `/terms`, `/privacy`, `/refunds`, `/promotion-rules`, `/contact`, `/coupon/[token]`.

### 4.2 Key components & behaviour

| Component | Requirements |
|---|---|
| `CampaignProgressCard` | Live `28/40` slots, `3/5` winners, remaining counts. Animated counters **only after data loads**. Never fabricate values. Polls or revalidates periodically. |
| `ServiceGrid` / `ServiceCard` | Image, name, short description, duration, price, Add/Remove, selected highlight, featured badge, optional category filter. |
| `SelectionCart` | Desktop side panel / mobile sticky bottom bar. Shows count, subtotal, discount unlocked state, savings, payable, Continue CTA. |
| `DiscountReveal` | Fires when the 2nd distinct service is added: brief glow, smooth price transition, "10% DISCOUNT UNLOCKED" badge. Must explain *why*. |
| `CheckoutDrawer` | Name, phone (required), email (per business decision), optional OTP step, server-computed summary, `Pay ₹405 Securely` CTA. React Hook Form + Zod. |
| `PaymentFlow` | Razorpay hosted/embedded checkout. **Never build a card form.** |
| `ProcessingStates` | Payment received → Verifying → Checking lucky slot → Generating coupon. Each state backed by a real server response, not a timer. |
| `WinnerReveal` | Short confetti (≤3s), reward services list, refund status, View Coupon. |
| `NonWinnerReveal` | Accurate and positive; shows the ₹ saved. **No deceptive near-win animation.** |
| `CouponView` | Salon name, coupon code, QR, first name, services, subtotal, discount, paid, lucky result, free entitlements, refund status, validity, status. Print/PDF/share. |

### 4.3 Design system

- Palette: deep charcoal background, warm ivory secondary, muted gold accent, accessible green/amber/red states.
- Type: elegant serif headings (Playfair/Cormorant class), clean sans body (Inter/Manrope class), with web-safe fallbacks.
- Breakpoints: 360 / 390 / 430 / 768 / 1024 / 1280 / 1440+. Mobile-first.
- Motion: subtle reveals, counter animation, discount badge, coupon reveal. No global parallax, no heavy video on low-end mobile. Target 60 FPS.
- Images: next/image, WebP/AVIF, responsive sizes, blur placeholders, lazy below fold, CDN.

### 4.4 Accessibility (required, not optional)

Keyboard navigation, visible focus rings, WCAG AA contrast, real form labels, screen-reader text, `aria-live` on checkout status transitions, full `prefers-reduced-motion` support.

### 4.5 SEO

Unique title, meta description, Open Graph, LocalBusiness + Service JSON-LD, canonical URL, sitemap, robots.txt, semantic headings, image alt text.

### 4.6 Frontend trust boundary

The browser may send **only `service_ids` and customer contact fields**. It must never send or be trusted for price, discount, total, lucky result, remaining slots, payment success, refund status or coupon validity.

---

## 5. Admin panel requirements

| Screen | Must have |
|---|---|
| Dashboard | Today's revenue, paid orders, slots `31/40`, winners `4/5`, discount given, lucky refunds, coupons redeemed, refunds pending. Charts: revenue by date, orders by hour, popular services, payment success/failure, slot utilisation, reward value, redemptions. |
| Services | Table (image, service, price, duration, status, featured, updated), add/edit/enable/disable/reorder/change image, price-change dialog that writes history automatically. |
| Campaign Settings | Capacity, lucky slots, discount %, min distinct services, max entries per phone, reward package picker, effective date. Shows the **"today is locked, changes apply from tomorrow"** banner when `paid_count >= 1`. |
| Payment Gateway | Provider, mode, masked key ID, secret fields (write-only), Test Connection, Save Securely, last-tested status. MFA re-auth gate. Secrets never returned. |
| Orders | Filters: date range, order ID, customer, phone, service, payment status, lucky result, coupon status, refund status, method, amount range. Columns per spec. |
| Payments | Provider status, method, verification state, reconciliation flags. |
| Coupons | Search by code/phone/order/QR; detail with state; Redeem/Cancel/View order/payment/refund by permission. |
| QR Scanner | Camera scanner for receptionist → valid coupon panel → REDEEM NOW → confirmation with timestamp → "Already Redeemed" on rescan. |
| Refunds | Refund ID, order, customer, amount, reason, provider, status, attempts, timestamps; failure reason visible to owner; permission-gated manual retry. |
| Customers | Search, order history, block/unblock with reason. |
| Reports & History | Full filter set, CSV/Excel export (async), optional PDF summary. |
| Audit Logs | Date, actor, action, entity, before/after (masked), IP, request ID; filterable. |
| Website Content | Salon name, logo, hero copy, phone, WhatsApp, address, hours, gallery, testimonials, FAQ, social links. Kept separate from financial/security config. |
| Users & Roles | OWNER-only CRUD, role assignment, MFA enforcement, session revocation. |

**RBAC summary**

| Capability | OWNER | MANAGER | RECEPTIONIST |
|---|:---:|:---:|:---:|
| Payment gateway config | ✅ | ❌ | ❌ |
| Campaign config | ✅ | ❌ | ❌ |
| Admin user management | ✅ | ❌ | ❌ |
| Price changes | ✅ | ✅ | ❌ |
| Service management | ✅ | ✅ | ❌ |
| Website content | ✅ | ✅ | ❌ |
| View orders/payments/refunds | ✅ | ✅ | today only |
| Manual refund | ✅ | ❌ | ❌ |
| Coupon redeem | ✅ | ✅ | ✅ |
| Reports & export | ✅ | ✅ | ❌ |
| Audit logs | ✅ | ❌ | ❌ |

---

## 6. Infrastructure & DevOps requirements

- **Dev:** Docker Compose — `frontend`, `backend`, `postgres`, `redis`, `celery-worker`, `celery-beat`, `mailhog` (optional).
- **Envs:** `local` / `staging` / `production`, each with separate DB, Redis, gateway keys, URLs, secrets, buckets, webhook endpoints. **Live keys never in local.**
- **CI on PR:** frontend lint → typecheck → unit tests → backend lint (ruff) → backend tests (pytest) → `makemigrations --check` → dependency vulnerability scan → Docker build.
- **CD on main:** build → test → push versioned image → deploy staging → smoke test → manual approval → production deploy.
- **Production:** Cloudflare (CDN + WAF) → frontend hosting → Django API → managed Postgres + Redis + Celery worker/beat + secret manager + object storage.
- **Backups:** daily DB backup, multiple retention points, offsite, encrypted, documented restore, monthly restore drill.
- **Log retention:** app logs 30–90 days, audit logs longer, payment records per accounting/legal policy.

---

## 7. Testing requirements

| Layer | Must cover |
|---|---|
| Backend unit | discount calc, quote calc, discount allocation rounding, refund calc, lucky position generation, eligibility, campaign config resolution, coupon state machine, permission matrix |
| Frontend unit | service selection, cart maths display, discount display, form validation, payment state UI |
| Integration | order creation, reservation, payment create/verify, webhook, lucky decision, coupon creation, refund creation, redemption — against Razorpay sandbox |
| **Concurrency** | 20 simultaneous checkouts at `paid=39, capacity=40` → exactly one admitted, count never exceeds 40. Simultaneous verify + webhook → exactly one LuckyDecision, one Coupon, ≤one Refund. Concurrent double coupon scan → one redemption. |
| **Lucky engine** | exactly W unique positions in 1..N; same seed reproduces; different seed differs; participant number assigned once; decision immutable; winner count never exceeds W |
| **Payment** | success, failure, abandoned checkout, duplicate callback, webhook-before-verify, verify-before-webhook, delayed webhook, provider error, amount mismatch, currency mismatch, unknown payment ID |
| **Refund** | reward-only winner, mixed reward + non-reward, discount allocation, partial refund, provider failure, retry success, duplicate request, already refunded |
| **Coupon** | active/expired/redeemed/cancelled/winner/normal, invalid token, random-token attack, double redemption, concurrent scan |
| **Security** | price tampering, total tampering, verify replay, webhook replay, forged signature, coupon URL guessing, privilege escalation (manager→owner, receptionist→pricing), CSRF, invalid CORS origin, brute-force login, SQLi, XSS, IDOR |

---

## 8. Locked decisions (V1)

Confirmed 2026-09-20. These are no longer assumptions — build to them.

### 8.1 Refund scope — **reward-attributable-only** ✅ LOCKED

When a customer wins a lucky slot:

- Refund **only the actual amount paid for purchased services that belong to the Lucky Reward Package**, measured *after* allocated discount (i.e. the line's `net_paid_paise`, not its list price).
- Services **outside** the reward package remain paid and are not refunded.
- Reward-package services the customer **did not** originally buy become **free coupon entitlements** (`kind = FREE_REWARD`).

Worked example — reward package is {Haircut, Shaving, Face Massage}, customer buys Haircut ₹300 + Hair Spa ₹800:

```
Subtotal                        ₹1100   (110000 paise)
10% discount (2 distinct)        -₹110   ( 11000 paise)
Total paid                      ₹990    ( 99000 paise)

Discount allocation (largest-remainder, proportional):
  Haircut   300/1100 -> ₹30    net paid ₹270   ( 27000 paise)
  Hair Spa  800/1100 -> ₹80    net paid ₹720   ( 72000 paise)

Winner outcome:
  Refund           ₹270   (Haircut is in the reward package -> refund its net paid)
  Remains paid     ₹720   (Hair Spa is outside the package)
  Free entitlements: Shaving, Face Massage  (in package, not purchased)
  Coupon entitlements: Hair Spa (PAID), Haircut/Shaving/Face Massage (FREE_REWARD)
```

**Rationale:** keeps `RefundCalculator`, accounting, coupon entitlement logic and gateway reconciliation clean. A whole-order refund would make the non-reward portion a gift and break reconciliation against what the customer actually consumed.

### 8.2 Marketing wording — **"Har Din 5 Lucky Slots"** ⚠️ owner sign-off pending

Engineering position, to be confirmed by the owner:

- The architecture is **immediate reveal + pre-generated winning positions**. Under that design the daily winner count is *at most* `lucky_count`; it is lower whenever participation falls short of the positions drawn. "5 Lucky Customers" is therefore not a promise the system can keep.
- Recommended: keep immediate reveal, advertise **"Har Din 5 Lucky Slots"**, and state the capacity behaviour plainly in the promotion rules.
- **If the owner insists on exactly 5 actual winners every day**, the architecture must change to an **end-of-day draw** — winners chosen from the day's actual participants after the campaign closes. That removes the immediate post-payment reveal, changes the coupon flow (coupon issued first, lucky result appended later), changes the refund trigger point, and requires a notification channel. This is a Phase 4/6 redesign, not a copy change. Flag it before Phase 4 begins.

### 8.3 Discount allocation — **largest-remainder, deterministic** ✅ LOCKED

Explicit backend requirement:

1. For each order line compute the exact proportional share: `line_total_paise * discount_paise / subtotal_paise`.
2. **Floor** each share to whole paise.
3. Distribute the leftover paise **one at a time** to the lines with the largest fractional remainder.
4. Tie-break deterministically on `order_item.id` (ascending) so the result is reproducible.

Enforced invariants — asserted in code at order creation and covered by property-based tests:

```
SUM(order_item.discount_alloc_paise) == order.discount_paise
SUM(order_item.net_paid_paise)       == order.total_paise
```

Property-based tests must sweep random baskets across varying service counts, prices, quantities and discount percentages. This is not cosmetic: the allocation feeds partial winner refunds under §8.1, so an off-by-one paise here becomes a reconciliation break against the gateway.

### 8.4 Remaining owner questions (non-blocking for Phase 1)

| # | Question | Working assumption |
|---|---|---|
| 1 | Is email required at checkout? | Optional; phone required |
| 2 | Is phone OTP mandatory before payment in MVP? | Built feature-flagged; enforced before redemption, optional before payment at launch |
| 3 | Coupon validity period? | 30 days, configurable per campaign config |
| 4 | Single salon now, or multi-branch soon? | Single salon; `salon_id` FK retained so multi-branch is additive |
| 5 | Admin panel: custom Next.js or Django admin? | Custom Next.js; Django admin disabled in production |
| 6 | Hosting target (VPS + Docker vs Vercel + managed backend)? | Docker Compose for dev; production target affects Phase 10 only |
| 7 | Do non-lucky customers' paid services also become a redeemable coupon? | Yes — the coupon is proof of prepayment for all customers |
| 8 | GST / invoicing requirement? | Not in MVP scope — flag if the salon is GST-registered |
