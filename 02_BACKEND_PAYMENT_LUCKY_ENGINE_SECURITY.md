# Salon Lucky Customer Platform
## Backend, Payment, Lucky Engine and Security Workflow

**Document:** 2 of 3  
**Purpose:** Detailed backend logic, transaction flow, payment integrity, lucky-customer logic, refund design, coupon security, concurrency, idempotency, and platform security.

---

# 1. Backend Design Goals

The backend must guarantee:

1. Price integrity.
2. Discount integrity.
3. Payment authenticity.
4. No duplicate coupons.
5. No duplicate winner decisions.
6. No duplicate refunds.
7. Daily slot capacity cannot be exceeded.
8. Lucky winner count cannot exceed configured count.
9. Current-day winner positions cannot be manipulated after campaign start.
10. Admin cannot see hidden future winning positions.
11. Complete audit history is preserved.
12. Coupon redemption is one-time and atomic.
13. Payment secrets are never exposed to frontend.
14. Payment card or UPI credentials are never stored.

---

# 2. Source of Truth Rules

## Frontend Is Never Trusted For

- Price.
- Discount.
- Total amount.
- Lucky result.
- Remaining slots.
- Payment success.
- Refund status.
- Coupon validity.
- Coupon redeemed state.

The frontend may send:

```json
{
  "service_ids": ["uuid-1", "uuid-2"]
}
```

The backend calculates everything else.

---

# 3. Quote Workflow

Endpoint:

```text
POST /api/v1/orders/quote
```

Request:

```json
{
  "service_ids": [
    "service-uuid-1",
    "service-uuid-2"
  ]
}
```

Backend:

1. Load active services.
2. Reject missing/inactive services.
3. Count distinct services.
4. Calculate subtotal.
5. Read current campaign discount configuration.
6. Apply discount if eligible.
7. Return quote with short expiration.

Example response:

```json
{
  "currency": "INR",
  "subtotal_paise": 45000,
  "discount_percent": 10,
  "discount_paise": 4500,
  "payable_paise": 40500,
  "eligible_for_discount": true
}
```

Important:

- Quote is informational.
- Order creation recalculates totals.
- Payment creation also verifies order amount.

---

# 4. Order Creation Workflow

Endpoint:

```text
POST /api/v1/orders
```

Backend transaction:

```text
BEGIN
  Load active daily campaign
  Validate customer eligibility
  Recalculate prices
  Recalculate discount
  Create order
  Create order item snapshots
COMMIT
```

Order item snapshot fields are critical:

```text
service_name_snapshot
unit_price_paise
quantity
line_total_paise
```

Why:

If admin changes Haircut from ₹300 to ₹350 tomorrow, yesterday's order must still show ₹300.

---

# 5. Slot Reservation

A customer must not consume a permanent daily campaign slot before payment.

Use temporary reservation.

Example:

```text
Reservation TTL: 10 minutes
```

Workflow:

```text
Checkout starts
    |
Lock DailyCampaign row
    |
Calculate:
paid_count + active_reservations
    |
If >= capacity:
reject "Today's slots are full"
    |
Create temporary reservation
    |
Unlock
```

Suggested PostgreSQL pattern:

```text
SELECT ... FOR UPDATE
```

Reservation states:

```text
ACTIVE
CONSUMED
EXPIRED
CANCELLED
```

---

# 6. Why Reservation Is Required

Without locking/reservations:

```text
Capacity = 40
Paid = 39
```

Five users can reach checkout simultaneously and all see one available slot.

Result:

```text
44 / 40
```

With row locking:

- Only one checkout transaction gets the last available capacity.
- Others receive "Today’s promotion is full."

---

# 7. Payment Provider Abstraction

Backend code should not directly depend on Razorpay everywhere.

Use:

```python
class PaymentGateway:
    def create_order(...):
        ...

    def verify_client_payment(...):
        ...

    def verify_webhook(...):
        ...

    def fetch_payment(...):
        ...

    def refund(...):
        ...
```

Providers:

```text
RazorpayGateway
CashfreeGateway
```

Business logic calls the interface.

---

# 8. Gateway Credential Storage

Never store live payment gateway secrets in plaintext application tables.

Recommended flow:

```text
Owner enters Key ID + Secret
        |
        v
Backend validates permission + MFA
        |
        v
Secret encrypted in secret manager/KMS/Vault
        |
        v
Database stores secret reference only
```

Example DB fields:

```text
provider = "razorpay"
mode = "live"
key_id_masked = "rzp_live_****K92A"
secret_reference = "secret://salon/123/razorpay/live"
webhook_secret_reference = "secret://salon/123/razorpay/webhook"
```

Never return the full secret to frontend after saving.

---

# 9. Payment Creation

Endpoint:

```text
POST /api/v1/payments/create
```

Backend:

1. Authenticate customer/order context.
2. Verify reservation still active.
3. Verify order not already paid.
4. Recalculate/confirm backend stored total.
5. Create provider order.
6. Store gateway order ID.
7. Return only safe checkout configuration.

Payment amount must come from backend DB, not request body.

---

# 10. Payment Verification

Use two layers:

## Layer 1 — Customer Return Verification

After successful client checkout:

```text
Frontend receives:
gateway_order_id
gateway_payment_id
signature
```

Send to:

```text
POST /api/v1/payments/verify
```

Backend:

- Recompute expected signature.
- Reject invalid signature.
- Fetch payment from provider if necessary.
- Verify amount.
- Verify currency.
- Verify gateway order ID.
- Mark payment as verified only when consistent.

## Layer 2 — Webhook

Provider webhook independently confirms payment.

Webhook endpoint:

```text
POST /api/v1/webhooks/razorpay
```

Never trust webhook before validating its signature.

---

# 11. Payment Idempotency

Gateways can send duplicate webhooks.

Example:

```text
payment.captured
payment.captured
payment.captured
```

System must still create:

```text
1 Payment
1 LuckyDecision
1 Coupon
0 or 1 Refund
```

Use unique constraints:

```text
UNIQUE(provider, gateway_event_id)
UNIQUE(gateway_payment_id)
UNIQUE(order_id) on LuckyDecision
UNIQUE(order_id) on Coupon
```

Processing:

```text
Receive webhook
    |
Verify signature
    |
Try insert event ID
    |
Already exists?
   / \
 Yes  No
 |     |
200   Process event
      |
      200
```

---

# 12. Payment State Machine

```text
CREATED
  |
  +--> FAILED
  |
  v
AUTHORIZED
  |
  v
CAPTURED
  |
  +--> PARTIALLY_REFUNDED
  |
  v
REFUNDED
```

Only verified/captured payments may participate in lucky result logic.

---

# 13. Lucky Engine Overview

Required behavior:

- Daily capacity = N.
- Lucky winners = W.
- W <= N.
- Winner positions are generated before customers participate.
- Customer gets a participant number only after valid payment.
- `participant_number` is sequential per daily campaign.
- Customer is winner if their participant number is in hidden winning positions.
- Hidden future winning positions are not visible in admin UI.

Example:

```text
Capacity = 40
Lucky Count = 5

Winning positions:
4, 11, 18, 29, 37
```

Customer sequence:

```text
#1  Non-winner
#2  Non-winner
#3  Non-winner
#4  Winner
...
```

---

# 14. Cryptographically Secure Seed

At daily campaign creation:

```text
secret_seed = cryptographically_secure_random_256_bits
```

Generate commitment:

```text
commitment =
SHA256(
    secret_seed
    + salon_id
    + campaign_date
    + capacity
    + lucky_count
)
```

Store:

```text
seed_commitment
encrypted_seed_reference
```

Optional audit after campaign close:

- Keep seed encrypted permanently.
- Or reveal seed to owner/internal auditor after campaign closure.
- Never reveal active campaign seed publicly.

---

# 15. Generating Winning Positions

Requirements:

- Deterministic from seed for audit.
- Uniform selection.
- No duplicates.
- Exactly W unique positions.

Pseudo workflow:

```text
PRNG seeded from secret_seed
sample W unique integers from 1..N
sort results
```

Example:

```text
N=40
W=5

=> [4, 11, 18, 29, 37]
```

Do not generate a winner independently after every payment with:

```python
random.randint(...)
```

because that can produce inconsistent totals and weak auditability.

---

# 16. Lucky Decision Transaction

After payment is securely verified:

```text
BEGIN

Lock DailyCampaign row

Check payment not already processed

Convert reservation to consumed

Increment paid_count

participant_number = paid_count

Determine:
participant_number in winning_positions?

Create LuckyDecision

If winner:
    increment winner_count

Create Coupon

COMMIT
```

All these actions must be in one database transaction.

---

# 17. Preventing Double Lucky Decisions

Unique constraint:

```text
UNIQUE(order_id)
```

If payment verification endpoint and webhook race with each other:

- One wins transaction.
- The other finds existing LuckyDecision.
- It returns the same existing result.

Never run the lucky algorithm twice for the same order.

---

# 18. Campaign Configuration Lock

Admin can configure:

```text
Daily capacity
Lucky count
Discount percent
Minimum distinct services
Reward package
Entry limit
```

Recommended rule:

```text
If campaign has zero paid participants:
    current-day config may be edited carefully

If campaign has >= 1 paid participant:
    current-day config is immutable
    change applies from next campaign date
```

Reason:

Changing winner count or capacity during the day can make campaign fairness questionable.

---

# 19. "Exactly Five Winners" Limitation

If winning positions are:

```text
4, 11, 18, 29, 37
```

and only 20 customers participate:

- Only positions 4, 11, 18 are reached.
- 3 customers actually win.
- 2 winning positions remain unused.

Therefore:

- If immediate post-payment result is required, market it as "5 Lucky Slots" or explain daily capacity rules.
- If exactly 5 real customers must win every day, winner selection must happen only after the campaign closes.

The project requirement prefers immediate result, so preselected lucky slots are recommended.

---

# 20. Reward Definition

Do not hard-code reward logic deeply.

Campaign reward configuration:

```text
reward_type = SERVICE_PACKAGE

services:
- Hair Cutting
- Shaving
- Face Massage
```

Potential future types:

```text
SERVICE_PACKAGE
FIXED_DISCOUNT
PERCENT_DISCOUNT
FIXED_CREDIT
```

For version 1, keep only `SERVICE_PACKAGE` active.

---

# 21. Winner Financial Flow

Problem:

Customer has already paid before lucky result.

Therefore a winner requires one of these models.

Recommended:

```text
Pay
 |
Winner
 |
Refund eligible amount
 |
Issue free-service entitlement coupon
```

Example:

Customer purchased:

```text
Haircut       ₹300
Hair Spa      ₹800
```

Reward package includes:

```text
Haircut
Shaving
Face Massage
```

Possible policy:

```text
Refund paid amount attributable to Haircut.
Hair Spa remains paid.
Coupon additionally grants Shaving + Face Massage free.
```

The exact rule must be defined clearly in promotion terms.

---

# 22. Refund Calculation

Never blindly refund entire order unless that is the official promotion policy.

Create a deterministic refund calculator.

Inputs:

```text
Order items
Discount allocation
Reward services
Already refunded amount
```

Outputs:

```text
eligible_refund_paise
free_service_entitlements
```

If 10% discount applied, allocate discount proportionally to service lines so the refund amount is financially consistent.

---

# 23. Refund State Machine

```text
NOT_REQUIRED
    |
    v
PENDING
    |
    +--> PROCESSING
            |
            +--> COMPLETED
            |
            +--> FAILED
                    |
                    v
                 RETRYING
```

Store provider refund ID.

Do not call refund API repeatedly without idempotency.

---

# 24. Refund Retry Strategy

Background worker:

```text
Attempt 1 immediately
Attempt 2 after 1 minute
Attempt 3 after 5 minutes
Attempt 4 after 30 minutes
Attempt 5 after 2 hours
```

Then:

```text
MANUAL_REVIEW_REQUIRED
```

All retry attempts go to structured logs and audit records.

---

# 25. Coupon Token Security

Do not create predictable URLs such as:

```text
/coupon/1
/coupon/2
/coupon/3
```

Use opaque high-entropy token.

Example:

```text
coupon_public_token = random 128+ bit token
```

URL:

```text
/coupon/{opaque_token}
```

The public coupon view should show only necessary data.

---

# 26. Coupon QR

QR should contain either:

```text
https://example.com/coupon/{opaque-token}
```

or another signed short verification URL.

Do not place:

- Phone.
- Email.
- Payment ID.
- Card information.
- Personal identity information.

directly into the QR payload.

---

# 27. Coupon Redemption

Staff scans QR.

Backend transaction:

```text
BEGIN

SELECT coupon FOR UPDATE

If status != ACTIVE:
    reject

If expired:
    mark EXPIRED
    reject

Validate services/entitlement

Create CouponRedemption

Set coupon.status = REDEEMED

COMMIT
```

Second attempt:

```text
Already redeemed
Date/time
```

No second redemption.

---

# 28. Phone Verification and Entry Limits

Recommended:

- Customer verifies phone via OTP before payment or before coupon issuance.
- Daily entry limit is configurable.

Example:

```text
Max lucky entries per phone per day = 1
```

A customer may be allowed to make more than one normal salon purchase, while only the first eligible order enters the lucky campaign.

Keep:

```text
purchase eligibility
```

separate from:

```text
lucky campaign eligibility
```

---

# 29. Abuse Prevention

Potential controls:

- Phone OTP.
- Rate limit by IP.
- Rate limit by phone.
- Device fingerprint only if privacy policy supports it.
- Duplicate payment detection.
- Same gateway payment ID cannot be reused.
- Max campaign entries per day.
- Block known abusive accounts manually.
- Coupon one-time redemption.
- No manual override of lucky result by normal staff.
- Owner override, if ever supported, requires explicit audited exceptional action.

---

# 30. Admin Roles

## OWNER

Can:

- Configure payment gateway.
- Configure campaigns.
- Manage admin users.
- Change prices.
- View all reports.
- Initiate/reforce allowed refund workflows.
- View audit logs.

## MANAGER

Can:

- Manage services.
- View customers/orders.
- View payments/refunds.
- View reports.
- Manage website content.

Cannot:

- Read payment secrets.
- Change owner credentials.
- Change secret-storage configuration.

## RECEPTIONIST

Can:

- Search coupon.
- Scan coupon.
- Redeem coupon.
- View today's bookings.

Cannot:

- Edit prices.
- Change campaign.
- View gateway credentials.
- View full financial configuration.

---

# 31. Admin Authentication

Recommended:

- Email + password.
- MFA required for owner.
- MFA strongly recommended for managers.
- Passkey support can be added later.
- Login attempt throttling.
- Account lock/cooldown after repeated failures.
- Secure password hashing.
- Password-reset tokens short-lived.

For web admin:

Use secure server-side authentication cookies:

```text
HttpOnly
Secure
SameSite=Lax or Strict where compatible
```

Avoid storing long-lived admin JWTs in browser localStorage.

---

# 32. CSRF Protection

If using cookie/session authentication:

- Enable Django CSRF.
- Include CSRF token on mutating requests.
- Reject missing/invalid token.
- Do not disable CSRF globally.

---

# 33. CORS

Recommended:

- Public frontend origin explicitly allowlisted.
- Admin origin explicitly allowlisted.
- No `*` wildcard in production for credentialed endpoints.
- API should not accept arbitrary origins.

---

# 34. HTTPS and Headers

Production headers:

```text
Strict-Transport-Security
Content-Security-Policy
X-Content-Type-Options: nosniff
Referrer-Policy
Permissions-Policy
```

Cookies:

```text
Secure
HttpOnly
SameSite
```

Redirect HTTP to HTTPS.

---

# 35. Content Security Policy

At minimum, explicitly allow:

- Self scripts.
- Required payment gateway scripts.
- Required payment gateway frames.
- Required CDN domains.
- Analytics only if actually used.

Avoid:

```text
script-src *
```

Where possible, use nonce-based CSP for inline scripts.

---

# 36. Secrets Policy

Never commit:

```text
Razorpay secret
Webhook secret
Django SECRET_KEY
Database password
Redis password
SMTP password
Cloud credentials
```

to Git.

Use:

- Environment injection.
- Secret manager.
- KMS.
- Deployment platform secrets.

Rotate secrets after staff access changes or suspected exposure.

---

# 37. Database Security

Production PostgreSQL:

- Private network only.
- No public internet access unless strictly controlled.
- Separate application user.
- Least privilege.
- TLS connection if remote.
- Automated backups.
- Point-in-time recovery if budget permits.
- Periodic restore tests.

---

# 38. Audit Logging

Audit sensitive events:

```text
ADMIN_LOGIN
ADMIN_LOGIN_FAILED
SERVICE_CREATED
SERVICE_UPDATED
SERVICE_PRICE_CHANGED
CAMPAIGN_CONFIG_CHANGED
PAYMENT_GATEWAY_CHANGED
PAYMENT_VERIFIED
PAYMENT_RECONCILED
LUCKY_DECISION_CREATED
REFUND_CREATED
REFUND_COMPLETED
COUPON_REDEEMED
ADMIN_CREATED
ROLE_CHANGED
```

Audit record:

```text
actor
action
entity type
entity ID
before values
after values
IP
user agent
request ID
timestamp
```

Never log:

- Full gateway secret.
- CVV.
- Card number.
- UPI PIN.
- OTP.

---

# 39. Structured Application Logs

Each request gets:

```text
request_id
```

Log example:

```json
{
  "level": "INFO",
  "event": "payment_verified",
  "request_id": "req_xxx",
  "order_id": "ord_xxx",
  "provider": "razorpay",
  "payment_id_last4": "K92A"
}
```

Never log sensitive raw payloads blindly.

---

# 40. Payment Webhook Payload Retention

Options:

- Store normalized fields.
- Store encrypted raw payload if needed for audit.
- Or store hash + selected normalized fields.

If raw payload contains sensitive information, encrypt it and define retention limits.

---

# 41. Daily Campaign Creation

Primary scheduled task:

```text
00:00 Asia/Kolkata
```

Workflow:

1. Close previous campaign.
2. Read latest config effective for today.
3. Create DailyCampaign.
4. Generate seed.
5. Generate winning positions.
6. Store encrypted secret/position representation.
7. Store seed commitment.
8. Mark ACTIVE.

---

# 42. Lazy Campaign Creation Fallback

Never rely only on cron/Celery.

Before campaign-dependent request:

```text
Does today's campaign exist?
```

If no:

```text
Create it atomically.
```

This handles scheduler outages.

Unique constraint on:

```text
(salon_id, campaign_date)
```

prevents duplicate daily campaigns.

---

# 43. Campaign Closure

At end of day:

- Mark campaign closed.
- Expire unused reservations.
- Calculate final statistics.
- Reconcile payments.
- Keep unused winner positions as unclaimed.
- Prevent further participation.
- Preserve record permanently.

---

# 44. Payment Reconciliation Job

Run periodically:

- Find payment records in uncertain state.
- Fetch provider status.
- Compare:
  - amount.
  - order ID.
  - currency.
  - capture status.
- Correct safe mismatches.
- Send suspicious records to manual review.

---

# 45. Failure Handling

## Payment succeeded but customer closed browser

Webhook completes:

- Payment verification.
- Lucky decision.
- Coupon creation.
- Refund creation if winner.

Customer can later reopen:

```text
/coupon/{token}
```

or retrieve via phone/order lookup.

## Payment succeeded but webhook delayed

Client verification can temporarily complete process after strong signature/provider verification.

Webhook later reconciles idempotently.

## Refund API unavailable

- Coupon still shows winner.
- Refund status shows pending.
- Background worker retries.
- Admin can see failure.

## Daily scheduler failed

First campaign request creates today's campaign atomically.

## Duplicate webhook

Ignored via unique event ID.

---

# 46. Important Database Constraints

Recommended:

```text
UNIQUE salon + campaign_date
UNIQUE provider + gateway_event_id
UNIQUE gateway_payment_id
UNIQUE order -> lucky_decision
UNIQUE order -> coupon
UNIQUE campaign + participant_number
```

Check constraints:

```text
daily_capacity > 0
lucky_count >= 0
lucky_count <= daily_capacity
discount_percent between 0 and 100
amount_paise >= 0
```

---

# 47. Sensitive Admin Actions Requiring Re-Authentication

Require MFA/re-auth for:

- Changing payment gateway.
- Revealing/regenerating secret references.
- Changing owner email.
- Adding another owner.
- Changing campaign lucky count after future scheduling.
- Manual refund outside normal winner workflow.
- Disabling audit-related protection.

---

# 48. API Rate Limits

Example production policy:

```text
Public GET:
moderate limit

Quote:
30/min/IP

Create order:
10/min/IP

OTP request:
3/10min/phone
5/10min/IP

Payment verify:
10/min/order

Coupon lookup:
30/min/IP

Admin login:
5/15min/account + IP
```

Exact values should be tuned after real traffic data.

---

# 49. Validation Strategy

Use validation at:

1. Frontend.
2. DRF serializer.
3. Domain service layer.
4. Database constraints.

Example:

Frontend:

```text
lucky_count <= daily_capacity
```

Backend repeats it.

Database enforces it.

---

# 50. Security Test Checklist

Before launch:

- SQL injection testing.
- XSS testing.
- CSRF testing.
- CORS testing.
- Auth bypass testing.
- IDOR testing.
- Rate-limit testing.
- Coupon replay testing.
- Duplicate webhook testing.
- Concurrent last-slot testing.
- Duplicate refund testing.
- Lucky result double-processing testing.
- Payment amount tampering testing.
- Service price tampering testing.
- Admin privilege escalation testing.
- Secret exposure review.
- Log exposure review.

---

# 51. Golden Backend Rule

Every money or promotion decision must be reproducible from persisted backend data.

For every order, the system should be able to prove:

```text
What services were selected?
What were their prices at the time?
Why was 10% discount applied or not applied?
Which campaign was active?
What participant number was assigned?
Was that position a winner?
What coupon was created?
What amount was refunded?
Who redeemed the coupon?
```

If that chain cannot be reconstructed later, the backend is not audit-ready.
