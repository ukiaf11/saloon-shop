# Salon Lucky Customer Platform
## Project Blueprint and System Architecture

**Document:** 1 of 3  
**Purpose:** High-level product, business, architecture, data model, modules, and end-to-end system blueprint.

---

# 1. Project Vision

Build a premium, mobile-first, single-page salon website with a separate secure owner/admin panel.

The website should:

- Present salon services, prices, packages, gallery, reviews, timing, location, and contact information.
- Promote a daily lucky-customer campaign.
- Allow customers to select salon services and pay using UPI or cards.
- Automatically provide a 10% discount when the customer selects at least 2 different services.
- Generate a coupon after a verified payment.
- Show whether the customer received the Lucky Free Service reward.
- Show public aggregate progress for today's campaign:
  - Daily slots filled.
  - Daily slots remaining.
  - Lucky customers selected.
  - Lucky customers remaining.
- Let the salon owner control services, prices, campaign settings, payment gateway settings, users, reports, history, and audit logs.
- Preserve complete daily history instead of deleting or resetting records.

---

# 2. Main Promotional Message

Recommended headline:

> **Har Din 5 Lucky Customers!**  
> Hair Cutting + Shaving + Face Massage FREE

For a technically safer implementation, the campaign can be communicated as:

> **Har Din 5 Lucky Slots!**  
> Eligible customers can win Hair Cutting + Shaving + Face Massage FREE.

This avoids promising five actual winners on a day when fewer customers participate than the configured daily capacity.

---

# 3. Core Business Rules

## 3.1 Service Pricing

- All prices are displayed in INR.
- Internally store money as integer paise.
- Example:
  - ₹300 = `30000`
  - ₹499 = `49900`
- Never use floating-point values for payment calculations.
- The backend is the source of truth for all prices.

## 3.2 Multi-Service Discount

Rule:

- Customer selects **2 or more different services**.
- The backend applies **10% discount** automatically.
- Multiple quantities of the same service do not count as multiple different services unless explicitly configured later.

Example:

```text
Hair Cutting       ₹300
Shaving            ₹150
------------------------
Subtotal            ₹450
10% Discount        -₹45
------------------------
Final Amount        ₹405
```

## 3.3 Daily Lucky Campaign

Example admin configuration:

```text
Daily Capacity:        40
Lucky Slots:            5
Reward Package:
- Hair Cutting
- Shaving
- Face Massage
```

Business rules:

- Daily lucky count must be less than or equal to daily capacity.
- Campaign configuration should be locked for the current day after the first valid paid participation.
- Any configuration changes after that should apply to the next day.
- A new immutable campaign record is created every day.
- Yesterday's record is never reset or overwritten.

## 3.4 Coupon

Every successful customer payment creates a coupon.

Coupon contains:

- Coupon ID/token.
- QR code.
- Customer-safe order information.
- Paid services.
- Discount amount.
- Payment status.
- Lucky result.
- Eligible free services if winner.
- Coupon status.
- Validity.
- Redemption status.

Coupon QR must use an opaque random token and must not expose personal information.

---

# 4. Recommended Technology Stack

## Frontend

- **Next.js**
- **TypeScript**
- **Tailwind CSS**
- **Motion / Framer Motion**
- Optional component system: shadcn/ui or equivalent
- React Hook Form + Zod for form validation

Why:

- Excellent SEO.
- Fast rendering.
- Strong mobile support.
- Good developer ecosystem.
- Great animation and responsive UI capabilities.

## Backend

- **Python**
- **Django**
- **Django REST Framework**
- PostgreSQL
- Redis
- Celery

Why:

- Strong security defaults.
- Mature admin and ORM ecosystem.
- Excellent transaction support.
- Good background-job support.
- Suitable for financial and audit-heavy business logic.

## Database

**PostgreSQL**

Used for:

- Customers.
- Services.
- Prices.
- Orders.
- Payments.
- Campaigns.
- Coupons.
- Refunds.
- Audit logs.
- Admin users.
- Historical reports.

## Cache and Queue

**Redis**

Used for:

- Rate limiting.
- Temporary checkout/session state.
- Queue backend.
- Non-critical cached analytics.
- Distributed locks where appropriate.

## Background Processing

**Celery**

Used for:

- Refund retries.
- Webhook retry tasks.
- Daily campaign initialization.
- Notifications.
- Export generation.
- Scheduled maintenance.

## Payment Gateway

Primary recommendation:

- Razorpay

Architecture requirement:

- Payment provider abstraction must be used so another gateway such as Cashfree can be added later without rewriting business logic.

## Infrastructure

Recommended:

- Docker
- Reverse proxy / Cloudflare
- Managed PostgreSQL if possible
- Managed Redis if possible
- Object storage for images/files
- Sentry or equivalent error monitoring
- Centralized structured logs
- Secret manager / KMS / Vault

---

# 5. High-Level Architecture

```text
CUSTOMER
   |
   v
Cloudflare / CDN / WAF
   |
   v
Next.js Public Website
   |
   v
Django REST API
   |
   +--------------------+
   |                    |
   v                    v
PostgreSQL            Redis
   |                    |
   |                    v
   |                Celery
   |                    |
   +----------+---------+
              |
              v
        Payment Gateway
       UPI / Cards / Refunds
              ^
              |
           Webhooks


OWNER / ADMIN
     |
     v
Secure Admin Application
     |
     v
Django REST API
```

---

# 6. Main Product Surfaces

## 6.1 Public Single-Page Website

Sections:

1. Hero.
2. Lucky campaign banner.
3. Today's progress.
4. Services.
5. Package/offer area.
6. Selection cart.
7. Discount reveal.
8. How Lucky Customer works.
9. Gallery.
10. Reviews.
11. Why choose us.
12. Opening hours.
13. Contact.
14. WhatsApp.
15. Location/map.
16. FAQ.
17. Terms links.
18. Footer.

## 6.2 Customer Checkout

Steps:

1. Select services.
2. Review selected services.
3. Auto-apply discount when eligible.
4. Enter minimum required customer details.
5. Reserve campaign capacity.
6. Create payment order.
7. Open gateway checkout.
8. Complete payment.
9. Verify payment.
10. Assign daily participant number.
11. Evaluate lucky result.
12. Generate coupon.
13. Start refund if winner reward requires refund.
14. Show result.

## 6.3 Admin Panel

Main navigation:

```text
Dashboard
Services
Orders
Payments
Lucky Campaigns
Coupons
Customers
Refunds
Reports
Website Content
Payment Gateway
Users & Roles
Audit Logs
Settings
```

---

# 7. Suggested Backend Modules

```text
backend/
|
|-- config/
|
|-- apps/
|   |-- accounts/
|   |-- salons/
|   |-- catalog/
|   |-- customers/
|   |-- orders/
|   |-- payments/
|   |-- promotions/
|   |-- coupons/
|   |-- refunds/
|   |-- analytics/
|   |-- content/
|   |-- audit/
|
|-- integrations/
|   |-- payments/
|       |-- base.py
|       |-- razorpay.py
|       |-- cashfree.py
|
|-- tasks/
|
|-- manage.py
```

---

# 8. Suggested Frontend Structure

```text
frontend/
|
|-- app/
|   |-- page.tsx
|   |-- terms/
|   |-- privacy/
|   |-- refunds/
|   |-- promotion-rules/
|   |-- coupon/[token]/
|   |-- admin/
|
|-- components/
|   |-- hero/
|   |-- services/
|   |-- campaign/
|   |-- cart/
|   |-- checkout/
|   |-- coupon/
|   |-- admin/
|
|-- lib/
|-- hooks/
|-- types/
|-- styles/
```

---

# 9. Core Database Entities

## Salon

```text
id
name
slug
timezone
currency
address
phone
email
status
created_at
updated_at
```

## Service

```text
id
salon_id
name
slug
description
price_paise
duration_minutes
image
is_active
is_featured
display_order
created_at
updated_at
```

## ServicePriceHistory

```text
id
service_id
old_price_paise
new_price_paise
changed_by
changed_at
```

## Customer

```text
id
name
phone
email
phone_verified_at
created_at
updated_at
```

## CampaignConfig

```text
id
salon_id
daily_capacity
lucky_count
discount_percent
min_distinct_services
max_entries_per_phone_per_day
reward_definition
effective_from
created_by
created_at
```

## DailyCampaign

```text
id
salon_id
campaign_date
capacity
lucky_count
discount_percent
min_distinct_services
status
seed_commitment
encrypted_seed_reference
paid_count
winner_count
created_at
closed_at
```

Unique:

```text
(salon_id, campaign_date)
```

## SlotReservation

```text
id
daily_campaign_id
customer_id
reservation_token
expires_at
status
created_at
```

## Order

```text
id
salon_id
customer_id
daily_campaign_id
public_order_number
subtotal_paise
discount_paise
total_paise
status
created_at
paid_at
```

## OrderItem

```text
id
order_id
service_id
service_name_snapshot
unit_price_paise
quantity
line_total_paise
```

## Payment

```text
id
order_id
provider
gateway_order_id
gateway_payment_id
amount_paise
currency
status
payment_method
verified_at
created_at
```

Unique fields:

```text
gateway_payment_id
```

## PaymentWebhookEvent

```text
id
provider
gateway_event_id
event_type
payload_hash
status
received_at
processed_at
```

Unique:

```text
(provider, gateway_event_id)
```

## LuckyDecision

```text
id
order_id
daily_campaign_id
participant_number
is_winner
decision_hash
created_at
```

Unique:

```text
(daily_campaign_id, participant_number)
order_id
```

## Coupon

```text
id
order_id
opaque_token
coupon_code
status
is_lucky_winner
valid_from
valid_until
created_at
```

## CouponRedemption

```text
id
coupon_id
redeemed_by
redeemed_at
location
notes
```

## Refund

```text
id
payment_id
provider_refund_id
amount_paise
reason
status
attempt_count
created_at
updated_at
```

## AuditLog

```text
id
actor_id
action
entity_type
entity_id
before_json
after_json
ip_address
user_agent
request_id
created_at
```

---

# 10. Main API Groups

## Public

```text
GET  /api/v1/services
GET  /api/v1/promotion/today
POST /api/v1/orders/quote
POST /api/v1/orders
POST /api/v1/payments/create
POST /api/v1/payments/verify
GET  /api/v1/coupons/{token}
```

## Webhooks

```text
POST /api/v1/webhooks/razorpay
```

## Admin

```text
GET    /api/v1/admin/dashboard
GET    /api/v1/admin/services
POST   /api/v1/admin/services
PATCH  /api/v1/admin/services/{id}

GET    /api/v1/admin/orders
GET    /api/v1/admin/payments
GET    /api/v1/admin/refunds
GET    /api/v1/admin/coupons

GET    /api/v1/admin/campaign-settings
PATCH  /api/v1/admin/campaign-settings

GET    /api/v1/admin/payment-gateway
PUT    /api/v1/admin/payment-gateway
POST   /api/v1/admin/payment-gateway/test

POST   /api/v1/admin/coupons/{id}/redeem

GET    /api/v1/admin/audit-logs
GET    /api/v1/admin/reports
```

---

# 11. Order State Machine

Suggested states:

```text
DRAFT
  |
  v
QUOTED
  |
  v
PAYMENT_PENDING
  |
  +----> PAYMENT_FAILED
  |
  v
PAID
  |
  v
LUCKY_DECIDED
  |
  +----> REFUND_PENDING
  |         |
  |         +--> REFUNDED
  |         +--> REFUND_FAILED
  |
  v
COUPON_ACTIVE
  |
  v
REDEEMED
```

---

# 12. Campaign State Machine

```text
SCHEDULED
   |
   v
ACTIVE
   |
   v
CLOSED
```

Important:

- Never modify a closed campaign.
- Do not expose hidden winning positions to admin.
- Current-day campaign configuration becomes immutable after first paid participant.

---

# 13. Coupon State Machine

```text
PENDING
  |
  v
ACTIVE
  |
  +----> EXPIRED
  |
  +----> CANCELLED
  |
  v
REDEEMED
```

Coupon redemption must be atomic.

---

# 14. Customer Journey

```text
Open website
    |
View services and Lucky campaign
    |
Select services
    |
10% discount auto-applied if eligible
    |
Enter basic details
    |
Reserve slot
    |
Create payment
    |
Pay via UPI/Card
    |
Backend verifies payment
    |
Assign participant number
    |
Evaluate Lucky result
    |
Generate coupon
    |
Winner?
  /     \
Yes      No
 |        |
Refund    Standard coupon
eligible  and paid services
amount
 |
Free reward entitlement
 |
Customer visits salon
 |
Coupon QR scanned
 |
Coupon redeemed
```

---

# 15. Admin Journey

```text
Owner logs in with MFA
    |
Dashboard
    |
Configure services and prices
    |
Configure future campaign settings
    |
Configure payment gateway
    |
View orders/payments/refunds
    |
Scan/redeem coupons
    |
Search complete history
    |
Export reports
    |
Review audit logs
```

---

# 16. Public Campaign Metrics

Safe to show:

```text
Today's Capacity:       40
Paid Entries:           28
Slots Remaining:        12
Lucky Winners Found:     3
Lucky Winners Remaining: 2
```

Do not show:

- Future winning positions.
- Customer phone numbers.
- Customer names.
- Payment IDs.
- Internal seed.
- Internal fraud signals.

---

# 17. Legal and Policy Pages

Even if the marketing experience is a single page, keep these as separate routes:

```text
/terms
/privacy
/refunds
/promotion-rules
/contact
```

The promotion rules should clearly define:

- Eligibility.
- Daily campaign timing.
- Daily capacity.
- Reward scope.
- Discount rules.
- Payment requirement.
- Refund behavior.
- Coupon validity.
- Redemption rules.
- Duplicate-entry policy.
- Failure/maintenance handling.
- Abuse/disqualification rules.

---

# 18. Non-Functional Requirements

## Performance

Target:

- Fast mobile page load.
- CDN for images/static assets.
- Lazy-load heavy media.
- Avoid blocking animation bundles.
- Cache service/catalog reads where safe.

## Reliability

- Idempotent webhooks.
- Database transactions.
- Automatic retries for safe background tasks.
- Payment reconciliation job.
- Health checks.
- Backup and restore procedure.

## Security

- HTTPS only.
- WAF.
- Strong admin authentication.
- MFA.
- RBAC.
- Secret manager.
- No card storage.
- No CVV storage.
- Server-side pricing.
- Anti-replay webhook logic.
- CSRF protection.
- Rate limits.
- Audit logs.

## Auditability

The platform should be able to answer:

- Who changed a service price?
- When was the campaign configuration changed?
- Which payment created this coupon?
- Why was this customer marked as winner?
- Was the winner configuration fixed before participation?
- Who redeemed the coupon?
- What was the original order price at payment time?

---

# 19. Recommended Development Phases

## Phase 1 — Foundation

- Repositories.
- Environment configuration.
- Django project.
- Next.js project.
- PostgreSQL.
- Redis.
- CI basics.
- Logging.

## Phase 2 — Catalog

- Services.
- Admin service CRUD.
- Price history.
- Public service API.

## Phase 3 — Quote and Order

- Service selection.
- Backend quote engine.
- 10% discount.
- Order snapshot logic.

## Phase 4 — Daily Campaign

- Config.
- Daily campaign creation.
- Slot reservation.
- Lucky slot generation.
- Commitment/audit logic.

## Phase 5 — Payments

- Provider abstraction.
- Razorpay.
- Checkout.
- Signature verification.
- Webhooks.
- Idempotency.

## Phase 6 — Lucky Result and Coupon

- Participant assignment.
- Winner evaluation.
- Coupon generation.
- QR page.
- Redemption.

## Phase 7 — Refunds

- Winner refund calculation.
- Refund API.
- Retry handling.
- Refund dashboard.

## Phase 8 — Admin

- Dashboard.
- Orders.
- Payments.
- Coupons.
- History.
- Reports.
- Audit logs.

## Phase 9 — Security Hardening

- MFA.
- RBAC.
- Rate limits.
- WAF.
- CSP.
- HSTS.
- Secret manager.
- Security testing.

## Phase 10 — Production

- Monitoring.
- Backups.
- Payment reconciliation.
- Runbooks.
- Performance testing.
- Launch checklist.

---

# 20. Final Architecture Decision

Recommended final stack:

```text
Frontend:
Next.js + TypeScript + Tailwind + Motion

Backend:
Python + Django + Django REST Framework

Database:
PostgreSQL

Cache / Queue:
Redis + Celery

Payments:
Razorpay behind a generic payment provider interface

Admin:
Custom Next.js admin dashboard

Security:
Cloudflare + HTTPS + MFA + RBAC + secure sessions +
secret manager + webhook HMAC/signatures + rate limits +
audit logs + DB transactions

Lucky Engine:
Pre-generated cryptographically secure daily winning
positions + participant numbering + immutable campaign history

Coupon:
Opaque token + QR + atomic one-time redemption

Daily Reset:
Create a new daily campaign record at midnight.
Never destroy previous campaign history.
```

---

# 21. Core Design Principle

The public website should remain visually simple and exciting.

All complex logic must remain server-side:

- Prices.
- Discounts.
- Campaign capacity.
- Winner determination.
- Payment verification.
- Refunds.
- Coupon state.
- Redemption.
- History.
- Audit trail.
- Security.

The browser should never be trusted with financial or lucky-result decisions.
