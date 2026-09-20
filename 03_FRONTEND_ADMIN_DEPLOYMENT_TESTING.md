# Salon Lucky Customer Platform
## Frontend, Admin UX, Deployment, Testing and Operations

**Document:** 3 of 3  
**Purpose:** Public UI/UX, admin experience, animations, responsive design, deployment, observability, testing, launch process, and operational workflow.

---

# 1. UI/UX Objective

The public website should feel like:

> Premium salon experience + modern fintech checkout

Avoid:

- Generic template look.
- Too many colors.
- Heavy animation that slows mobile devices.
- Showing raw API JSON.
- Showing technical payment IDs to customers.
- Cluttered multi-page navigation.

Use:

- Strong visual hierarchy.
- Large service imagery.
- Premium typography.
- Smooth but subtle animation.
- Clear pricing.
- High-trust payment UI.
- Immediate feedback.

---

# 2. Recommended Visual Direction

## Color System

Suggested:

```text
Primary background:
Deep charcoal / black-brown

Secondary:
Warm ivory / off-white

Accent:
Muted gold / champagne

Success:
Accessible green

Warning:
Amber

Error:
Accessible red
```

Exact brand colors can be adjusted later.

## Typography

Use:

- Elegant serif for major headings.
- Clean sans-serif for body, pricing, buttons, forms.

Example pairing:

```text
Heading: Playfair Display / Cormorant / equivalent
Body: Inter / Manrope / equivalent
```

Use web-safe fallback stacks.

---

# 3. Public Single-Page Layout

Recommended sequence:

```text
Navbar
 |
Hero
 |
Today's Lucky Campaign
 |
Services
 |
Sticky Service Selection Summary
 |
Discount Reveal
 |
How It Works
 |
Premium Packages
 |
Gallery
 |
Testimonials
 |
Why Choose Us
 |
Opening Hours
 |
Location
 |
FAQ
 |
Policies
 |
Footer
```

---

# 4. Header

Desktop:

```text
[Logo]  Services  Offers  Gallery  Contact    [Book Now]
```

Mobile:

```text
[Logo]                              [Menu]
```

Sticky header is acceptable but keep height small.

Primary CTA:

```text
Book Now
```

Secondary CTA:

```text
View Services
```

---

# 5. Hero Section

Recommended content:

```text
PREMIUM GROOMING. DAILY REWARDS.

Har Din 5 Lucky Customers!

Hair Cutting + Shaving + Face Massage
FREE

[Book Now]  [View Services]
```

Background options:

- Professional salon photo.
- Short muted looping salon video.
- Layered barber/salon still images.

Avoid auto-playing audio.

---

# 6. Lucky Campaign Card

Display:

```text
TODAY'S LUCKY OFFER

28 / 40
Paid Slots Filled

3 / 5
Lucky Customers Found

12 Slots Remaining

[Choose Your Services]
```

Use animated counters only after data loads.

Never fake progress values.

---

# 7. Services Section

Card example:

```text
+------------------------+
| [Service Image]        |
| Hair Cutting           |
| Precision styling      |
|                        |
| ₹300                   |
|                 [+ Add]|
+------------------------+
```

Features:

- Add/remove.
- Quantity only if needed.
- Highlight selected services.
- Category filter if service count becomes large.
- Featured badge.
- Duration.
- Small service description.

---

# 8. Sticky Selection Cart

On desktop:

- Side panel.

On mobile:

- Sticky bottom bar.

Example:

```text
2 Services Selected
₹450

10% Discount Unlocked
You save ₹45

Payable ₹405

[Continue]
```

This is a strong conversion feature.

---

# 9. Discount Animation

When second distinct service is selected:

```text
10% DISCOUNT UNLOCKED
```

Animation:

- Brief glow.
- Price transitions smoothly.
- Small badge appears.
- No excessive confetti before purchase.

The customer should understand exactly why the discount appeared.

---

# 10. How Lucky Offer Works

Use 4 simple steps:

```text
1. Select Services
2. Pay Securely
3. Get Your Lucky Result
4. Show Coupon at Salon
```

Small disclaimer:

```text
Daily promotional capacity and campaign rules apply.
```

Link:

```text
View Promotion Rules
```

---

# 11. Checkout Drawer / Modal

Fields:

```text
Name
Phone
Email (optional or required based on business decision)
```

Recommended:

- Phone required.
- OTP verification optional before payment for MVP, strongly recommended before final coupon use.
- Email optional unless receipts are emailed.

Summary:

```text
Hair Cutting        ₹300
Shaving             ₹150
-------------------------
Subtotal             ₹450
10% Offer            -₹45
-------------------------
Payable              ₹405
```

CTA:

```text
Pay ₹405 Securely
```

---

# 12. Payment Experience

Never build your own card form.

Use payment gateway hosted/embedded checkout.

Customer sees:

- UPI.
- Cards.
- Supported payment methods from gateway.

Before payment:

```text
Secure Payment
```

After payment button click:

```text
Creating secure payment...
```

Do not show internal processing details.

---

# 13. Payment Success Processing UI

Recommended step animation:

```text
Payment received ✓
      |
Verifying payment...
      |
Checking today's Lucky Slot...
      |
Generating your coupon...
```

These are UI states backed by real server responses, not fake timers.

---

# 14. Lucky Winner Reveal

Winner screen:

```text
🎉 YOU'RE A LUCKY WINNER!

Hair Cutting
Shaving
Face Massage

FREE

Refund Status:
Initiated

[View Coupon]
```

Animation:

- Short confetti.
- Glowing border.
- Coupon slides in.

Do not make animation longer than a few seconds.

---

# 15. Non-Winner Reveal

Positive but accurate:

```text
Payment Successful ✓

Today's Lucky Result:
Not selected

You still saved ₹45
with the Multi-Service 10% Offer.

[View Coupon]
```

Do not use deceptive near-win animations.

---

# 16. Coupon Page

Route:

```text
/coupon/{opaque-token}
```

Display:

```text
Salon Name
Coupon Code
QR
Customer first name
Services
Original subtotal
Discount
Paid amount
Lucky result
Free-service entitlement
Refund status
Coupon validity
Coupon status
```

Avoid exposing:

- Full gateway payment ID.
- Internal database IDs.
- Private audit fields.
- Hidden campaign data.

---

# 17. Coupon Print/Share

Optional:

- Save as PDF.
- Print.
- Share coupon link.
- Add to wallet in future.

If share link is supported, opaque token must have enough entropy.

---

# 18. Accessibility

Required:

- Keyboard navigation.
- Focus indicators.
- Accessible contrast.
- Form labels.
- Screen-reader text.
- `aria-live` for checkout status where appropriate.
- Reduced-motion support.

Honor:

```css
@media (prefers-reduced-motion: reduce)
```

Disable non-essential movement.

---

# 19. Admin UX Principles

Admin panel should prioritize:

1. Today's status.
2. Payments.
3. Coupons.
4. Refunds.
5. Campaign control.
6. Service pricing.
7. History.
8. Auditability.

Avoid hiding critical information behind many nested menus.

---

# 20. Admin Dashboard

Cards:

```text
Today's Revenue       ₹12,450
Paid Orders                 31
Campaign Slots           31/40
Lucky Winners             4/5
Discount Given          ₹1,380
Lucky Refunds           ₹2,490
Coupons Redeemed            18
Refunds Pending               1
```

Charts:

- Revenue by date.
- Orders by hour.
- Popular services.
- Payment success/failure.
- Slot utilization.
- Lucky reward value.
- Coupon redemption.

---

# 21. Services Admin

Table columns:

```text
Image
Service
Price
Duration
Status
Featured
Updated
Actions
```

Actions:

```text
Add
Edit
Disable
Enable
Reorder
Change image
Change price
```

Price change dialog:

```text
Current: ₹300
New:     ₹350

Effective immediately?

[Cancel] [Update Price]
```

Create price-history record automatically.

---

# 22. Campaign Settings Admin

Form:

```text
Daily Promotion Capacity
[40]

Lucky Slots
[5]

Multi-Service Discount
[10] %

Minimum Different Services
[2]

Max Lucky Entries per Phone
[1]

Reward Package
[x] Hair Cutting
[x] Shaving
[x] Face Massage

Effective Date
[Tomorrow]

[Save]
```

If today's campaign already has paid participants:

```text
Today's campaign is locked.
Changes will apply from tomorrow.
```

---

# 23. Payment Gateway Admin

Recommended UI:

```text
Provider
[Razorpay v]

Mode
[Test / Live]

Key ID
[****************92A]

Key Secret
[••••••••••••••••]

Webhook Secret
[••••••••••••••••]

[Test Connection]
[Save Securely]
```

After save:

- Do not return secret.
- Show masked Key ID.
- Show connection status.
- Show last tested date.
- Show webhook status if possible.

High-risk actions require MFA/re-auth.

---

# 24. Orders Page

Filters:

```text
Date range
Order ID
Customer
Phone
Service
Payment status
Lucky result
Coupon status
Refund status
Payment method
Amount range
```

Columns:

```text
Order
Customer
Services
Subtotal
Discount
Paid
Payment
Lucky
Coupon
Refund
Created
```

---

# 25. Coupon Management

Search by:

- Coupon code.
- Customer phone.
- Order number.
- QR scan.

Coupon detail:

```text
ACTIVE
REDEEMED
EXPIRED
CANCELLED
```

Actions based on permission:

```text
Redeem
Cancel
View order
View payment
View refund
```

---

# 26. QR Scanner Admin

For receptionist:

```text
[Open Camera Scanner]
```

After scan:

```text
VALID COUPON

Winner: Yes
Services:
- Hair Cutting
- Shaving
- Face Massage

[REDEEM NOW]
```

After redemption:

```text
Coupon redeemed successfully.
20 Sep 2026, 4:31 PM
```

Second scan:

```text
Already Redeemed
```

---

# 27. Refund Admin

Columns:

```text
Refund ID
Order
Customer
Amount
Reason
Provider
Status
Attempts
Created
Updated
```

Statuses:

```text
Pending
Processing
Completed
Failed
Manual Review
```

Owner can inspect failure reason.

Manual retry requires permission.

---

# 28. History and Reports

Filters:

```text
Date range
Customer
Phone
Service
Order ID
Payment ID
Coupon
Winner/Non-winner
Paid/Failed/Refunded
Redeemed/Active/Expired
UPI/Card
Discount applied
Amount range
```

Export:

```text
CSV
Excel
```

Optional:

```text
PDF summary report
```

---

# 29. Audit Log Admin

Columns:

```text
Date
Actor
Action
Entity
Before
After
IP
Request ID
```

Sensitive values masked.

Example:

```text
Action:
SERVICE_PRICE_CHANGED

Before:
₹300

After:
₹350
```

---

# 30. Website Content Management

Owner can edit:

- Salon name.
- Logo.
- Hero heading.
- Hero description.
- Phone.
- WhatsApp.
- Address.
- Hours.
- Gallery.
- Testimonials.
- FAQ.
- Social links.

Avoid putting sensitive backend configuration in the same UI section.

---

# 31. Responsive Breakpoints

Design mobile-first.

Support at minimum:

```text
360px
390px
430px
768px
1024px
1280px
1440px+
```

Test popular Android and iPhone viewport sizes.

---

# 32. Animation Guidelines

Good:

- Fade/slide section reveal.
- Subtle image zoom.
- Counter animation.
- Discount badge transition.
- Coupon reveal.
- Small winner confetti.

Avoid:

- Large parallax on all sections.
- Constant floating objects.
- Long forced animation before checkout.
- Heavy video backgrounds on low-end mobile devices.

Target 60 FPS where practical.

---

# 33. Image Optimization

Use:

- Next.js image optimization.
- WebP/AVIF.
- Correct responsive sizes.
- Lazy loading below fold.
- Blur placeholders.
- CDN.

Avoid multi-megabyte hero images.

---

# 34. SEO

Even for a single-page salon website:

- Unique page title.
- Meta description.
- Open Graph.
- Local business schema.
- Service schema where appropriate.
- Canonical URL.
- Sitemap.
- Robots.txt.
- Semantic headings.
- Accessible image alt text.

---

# 35. Local Business Content

Useful public information:

- Salon name.
- Phone.
- Address.
- Business hours.
- Maps link.
- WhatsApp booking link.
- Services and pricing.
- Reviews.
- Gallery.
- FAQs.

Do not require payment to simply view salon information.

---

# 36. Deployment Architecture

Recommended simple production setup:

```text
Cloudflare
    |
    v
Frontend Hosting / Reverse Proxy
    |
    v
Next.js
    |
    v
Django API
    |
    +--> PostgreSQL
    +--> Redis
    +--> Celery Worker
    +--> Celery Beat
    +--> Secret Manager
    +--> Object Storage
    +--> Payment Gateway
```

---

# 37. Docker Services

Development:

```text
frontend
backend
postgres
redis
celery-worker
celery-beat
```

Production can use managed PostgreSQL/Redis instead of containers.

---

# 38. Environment Separation

Maintain:

```text
local
staging
production
```

Separate:

- Database.
- Redis.
- Gateway keys.
- URLs.
- secrets.
- storage buckets.
- webhook endpoints.

Never use live payment keys in local development.

---

# 39. CI Pipeline

On pull request:

1. Lint frontend.
2. Type-check frontend.
3. Frontend unit tests.
4. Backend lint.
5. Backend tests.
6. Migration check.
7. Security dependency check.
8. Build Docker images.

On main/release:

1. Build.
2. Run tests.
3. Push versioned image.
4. Deploy staging.
5. Smoke test.
6. Manual approval.
7. Production deploy.

---

# 40. Migration Safety

Before deployment:

- Back up DB.
- Review destructive migrations.
- Prefer additive migrations.
- Deploy schema before code if needed.
- Avoid long table locks during business hours.

---

# 41. Monitoring

Monitor:

```text
API error rate
Response latency
Payment verification failures
Webhook failures
Refund failures
Campaign creation failures
Coupon redemption errors
Database CPU/storage
Redis availability
Celery queue size
```

Use alerting for critical failures.

---

# 42. Suggested Alerts

Immediate alert:

- Payment webhook signature failures spike.
- Refund failures exceed threshold.
- Today's campaign missing after configured start.
- Database unavailable.
- Payment provider errors spike.
- Coupon redemption endpoint failing.
- Admin login brute-force detected.

Non-urgent alert:

- Low disk/storage.
- Background queue growing.
- Image upload failures.
- Export task failures.

---

# 43. Backups

Minimum:

- Daily database backup.
- Multiple retention points.
- Offsite copy.
- Encryption.
- Documented restore procedure.

Better:

- Point-in-time recovery.
- Monthly restore drill.

A backup is only useful if restore is tested.

---

# 44. Logging Retention

Suggested:

```text
Application logs:
30-90 days depending on cost

Audit logs:
Longer retention

Payment/reconciliation records:
As required by business/accounting/legal policy
```

Do not retain unnecessary personal information indefinitely.

---

# 45. Test Strategy

## Unit Tests

Backend:

- Discount calculation.
- Quote calculation.
- Refund calculation.
- Lucky position generation.
- Eligibility.
- Campaign configuration.
- Coupon state.
- Permission rules.

Frontend:

- Service selection.
- Cart.
- Discount display.
- Form validation.
- Payment state UI.

---

# 46. Integration Tests

Test:

- Order creation.
- Reservation.
- Payment creation.
- Payment verification.
- Webhook.
- Lucky decision.
- Coupon creation.
- Refund creation.
- Coupon redemption.

Use sandbox/test payment environment.

---

# 47. Concurrency Tests

Critical:

## Last Slot

```text
capacity = 40
paid = 39
```

Send 20 simultaneous checkout reservation requests.

Expected:

- Exactly one valid final reservation within capacity.
- No campaign count above 40.

## Same Payment

Send payment verification and webhook at same time.

Expected:

- One LuckyDecision.
- One Coupon.
- One Refund maximum.

---

# 48. Security Tests

Test:

- Modify price in browser request.
- Modify total in request.
- Replay payment verification.
- Replay webhook.
- Forge webhook signature.
- Access another customer's coupon by guessing URL.
- Redeem same coupon twice.
- Manager attempts owner-only endpoint.
- Receptionist attempts price change.
- CSRF request.
- Invalid CORS origin.
- Brute-force login.

---

# 49. Lucky Engine Tests

For many campaigns:

```text
capacity = N
winners = W
```

Verify:

- Exactly W unique winning positions generated.
- All positions in range 1..N.
- Same seed/config reproduces same positions.
- Different seed usually produces different set.
- Participant number assigned once.
- Winner decision cannot change later.
- Winner count never exceeds W.

---

# 50. Payment Tests

Test:

```text
Success
Failure
Customer closes checkout
Duplicate callback
Webhook before client verification
Client verification before webhook
Webhook delayed
Provider temporary error
Amount mismatch
Currency mismatch
Unknown payment ID
```

---

# 51. Refund Tests

Test:

```text
Winner with only reward services
Winner with reward + non-reward services
10% discount allocation
Partial refund
Provider failure
Retry success
Duplicate refund request
Already refunded
```

---

# 52. Coupon Tests

Test:

```text
Active coupon
Expired coupon
Redeemed coupon
Cancelled coupon
Winner coupon
Normal coupon
Invalid token
Random token attack
Double redemption
Concurrent double scan
```

---

# 53. UAT Scenarios

Owner should validate:

1. Add service.
2. Change service price.
3. Configure 40 daily slots.
4. Configure 5 lucky slots.
5. Configure reward services.
6. Perform test UPI/card payment.
7. See lucky result.
8. See coupon.
9. Scan coupon.
10. Redeem coupon.
11. Verify history.
12. Export report.
13. Verify refund.
14. Change campaign for tomorrow.
15. Confirm today's campaign remains unchanged.

---

# 54. Launch Checklist

Before live payment activation:

```text
[ ] Production domain
[ ] HTTPS valid
[ ] WAF enabled
[ ] Admin MFA enabled
[ ] Production DB private
[ ] Backups enabled
[ ] Restore tested
[ ] Production Redis protected
[ ] Secrets moved to secret manager
[ ] Payment live credentials added
[ ] Webhook secret configured
[ ] Webhook signature verification enabled
[ ] Duplicate webhook test passed
[ ] Amount tampering test passed
[ ] Lucky concurrency test passed
[ ] Coupon replay test passed
[ ] Refund test passed
[ ] Terms published
[ ] Privacy policy published
[ ] Refund policy published
[ ] Promotion rules published
[ ] Monitoring enabled
[ ] Alerts enabled
[ ] Error tracking enabled
```

---

# 55. Daily Owner Operational Workflow

Morning:

```text
Open dashboard
Check today's campaign:
- capacity
- winner count
- payment gateway connected
- no pending critical refund failures
```

During day:

```text
Monitor orders
Redeem coupons
Handle customers
Review failed payments if needed
```

End of day:

```text
Review:
- revenue
- paid orders
- discount value
- lucky winners claimed
- refund totals
- coupon redemptions
```

The system closes the daily campaign automatically.

---

# 56. Incident Runbook Examples

## Payment gateway down

- Disable new checkout temporarily.
- Keep public site available.
- Show clear "payments temporarily unavailable" message.
- Do not create fake success orders.
- Retry gateway health check.
- Alert owner/admin.

## Refund failures

- Mark refund pending/failed.
- Retry automatically.
- Show correct status to admin/customer.
- Never hide failed refund.
- Escalate after retry limit.

## Database issue

- Put checkout into maintenance mode.
- Do not accept payments if order persistence is unavailable.
- Restore service.
- Reconcile gateway payments after recovery.

## Campaign initialization failure

- Lazy creation on first request.
- Alert engineering/admin.
- Verify daily config integrity.

---

# 57. Future Enhancements

After stable MVP:

- Online appointment scheduling.
- Employee/barber selection.
- Time-slot booking.
- WhatsApp confirmations.
- SMS reminders.
- Loyalty points.
- Membership plans.
- Gift cards.
- Customer login.
- PWA.
- Apple/Google Wallet coupon.
- Multiple branches.
- Multi-tenant SaaS model.
- Inventory.
- Staff commission.
- CRM segmentation.
- Marketing automation.

Do not add these before payment, coupon, campaign, refund, and audit flows are stable.

---

# 58. Recommended MVP Scope

Launch with:

```text
Public single page
Services
10% multi-service discount
Daily Lucky campaign
UPI/card payment
Coupon
QR verification
Winner refund
Service management
Campaign management
Payment settings
Orders
Payments
Coupons
Refunds
History
Audit logs
MFA
Backups
Monitoring
```

Delay non-essential features.

---

# 59. Final UX Rule

The customer should never need to understand:

- Webhooks.
- Payment signatures.
- Campaign seeds.
- Refund APIs.
- Reservation locks.
- Idempotency.
- Internal IDs.

They should only see:

```text
Choose Services
Get Discount
Pay Securely
See Lucky Result
Use Coupon
```

All complexity stays behind the UI.
