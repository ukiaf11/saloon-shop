# Salon Lucky Customer Platform — Implementation Plan

**Companion to:** `REQUIREMENTS.md`
**Created:** 2026-09-20
**Baseline:** greenfield — three specification documents, zero code.
**Assumed team:** 1–2 full-stack developers. Estimates are dev-days for one developer; parallel work is noted per phase.

---

## Strategy

The build order is driven by **risk**, not by screen count. The three things that can genuinely lose money or break trust are:

1. the **capacity/reservation race** (overselling the daily campaign),
2. the **payment verify ↔ webhook race** (double coupons, double refunds),
3. the **lucky engine** (unauditable or manipulable winner selection).

All three are backend concerns, so the backend domain core is built and concurrency-tested *before* the marketing UI is polished. The public page is built early but with mock data, so design work can proceed in parallel without blocking on the payment integration.

**Guiding rule for every phase:** if a money or promotion decision cannot be reconstructed from persisted data afterwards, the phase is not done.

---

## Phase overview

| # | Phase | Days | Depends on | Can parallelise with |
|---|---|---:|---|---|
| 0 | Decisions & accounts | 1 | — | — |
| 1 | Foundation & scaffolding | 3–4 | 0 | — |
| 2 | Catalog & content | 4–5 | 1 | 3F |
| 3 | Quote & order engine | 4–5 | 2 | 4F |
| 4 | Daily campaign & lucky engine | 5–6 | 3 | 6F |
| 5 | Payments (Razorpay) | 6–8 | 4 | 7F |
| 6 | Lucky result & coupons | 4–5 | 5 | — |
| 7 | Refunds | 3–4 | 6 | — |
| 8 | Admin panel | 8–10 | 2–7 | — |
| 9 | Security hardening | 4–5 | 8 | — |
| 10 | Production & launch | 4–5 | 9 | — |
| | **Total** | **~46–58 dev-days** | | |

"F" = the frontend half of that phase.
Realistic calendar for one developer: **10–12 weeks**. For two (one backend-leaning, one frontend-leaning): **6–7 weeks**.

---

## Phase 0 — Decisions & account setup (runs in parallel with Phase 1)

Phase 0 is **not** an engineering blocker. It runs on the owner/business and external tracks while engineering builds Phase 1.

**Decided 2026-09-20** (see `REQUIREMENTS.md` §8):
- ✅ Refund scope: **reward-attributable-only** — refund the `net_paid_paise` of purchased reward-package lines; non-package services stay paid; unpurchased package services become free entitlements.
- ✅ Discount allocation: **largest-remainder**, floor then distribute leftover paise by largest fractional remainder, tie-break on `order_item.id`, with two hard sum invariants.
- ⚠️ Marketing wording: **"Har Din 5 Lucky Slots"** recommended — awaiting owner sign-off. If the owner requires exactly 5 real winners daily, Phase 4/6 must be redesigned around an end-of-day draw (no immediate reveal). **Resolve before Phase 4 starts.**

**Still open on the business track:**
- [ ] Owner approves the "5 Lucky Slots" wording.
- [ ] Finalise promotion rules and refund policy text for legal review (long lead time).
- [ ] Answer the 8 non-blocking questions in `REQUIREMENTS.md` §8.4.

**Still open on the external track:**
- [ ] Razorpay onboarding: account, test keys, staging webhook URL.
- [ ] Sentry project, object storage bucket.
- [ ] Collect salon content: logo, service list with prices, photos, address, hours.

**Done when:** the wording decision is signed off (before Phase 4) and Razorpay test keys are in hand (before Phase 5).

---

## Phase 1 — Foundation & scaffolding (3–4 days) ✅ COMPLETE 2026-09-20

**Backend**
- [ ] Django project with split settings (`base`/`local`/`staging`/`production`), `django-environ`.
- [ ] App skeletons per `REQUIREMENTS.md` §3.1 — empty but wired into `INSTALLED_APPS`.
- [ ] `common/` utilities: money helpers (paise-only, no float), `request_id` middleware, structured JSON logging, base exceptions, idempotency helper, `select_for_update` lock helper.
- [ ] DRF configured: versioned `/api/v1/`, pagination, exception handler, throttle scaffolding.
- [ ] Celery + Beat wired to Redis; one no-op heartbeat task proving the whole chain works.
- [ ] `Salon` + `AdminUser` models and initial migration; management command to seed the salon and an owner.

**Frontend**
- [ ] Next.js (App Router) + TypeScript strict + Tailwind + Motion.
- [ ] Design tokens: charcoal/ivory/gold palette, serif+sans type scale, spacing scale, `prefers-reduced-motion` utilities.
- [ ] API client with typed fetch wrapper, error normalisation, Zod response validation.
- [ ] Base layout, navbar, footer, route shells for the legal pages.

**Infra**
- [ ] `docker-compose.yml`: frontend, backend, postgres, redis, celery-worker, celery-beat.
- [ ] `.env.example` for every service; `.gitignore` covering all secret file patterns.
- [ ] CI pipeline: ruff, pytest, `makemigrations --check`, eslint, tsc, next build.
- [ ] Pre-commit hooks including a secret scanner.

**Done when:** `docker compose up` gives a running site hitting a running API, and CI is green on an empty PR.

---

## Phase 2 — Catalog & content (4–5 days) ✅ COMPLETE 2026-09-20

**Backend**
- [ ] `Service`, `ServiceCategory`, `ServicePriceHistory`, `BusinessHour` models + constraints.
- [ ] Price-history hook: any `price_paise` change writes a history row with actor and reason — enforced in the service layer, covered by a test that fails if bypassed.
- [ ] `GET /api/v1/services`, `GET /api/v1/salon` with Redis caching and explicit invalidation on write.
- [ ] Content models: `SiteContent`, `GalleryImage`, `Testimonial`, `FaqItem`, `LegalPage` (versioned).
- [ ] Image upload to object storage with validation (type, size, dimensions).
- [ ] Seed fixture with the salon's real services.

**Frontend**
- [ ] Hero, Services grid, Gallery, Testimonials, Why Choose Us, Opening Hours, Location, FAQ, Footer — all driven by real API data.
- [ ] next/image pipeline: AVIF/WebP, responsive sizes, blur placeholders, lazy below fold.
- [ ] Legal pages rendering `LegalPage` markdown.
- [ ] SEO: metadata, Open Graph, LocalBusiness + Service JSON-LD, sitemap, robots.

**Tests:** service serialization, price-history creation, cache invalidation, content CRUD.

**Done when:** the public page renders the real salon with real services and scores well on Lighthouse mobile.

**Outcome:** done except the Lighthouse measurement, which needs a CI/device run.
Six public endpoints live and contract-verified; 146 tests pass. Carried forward:
legal pages are drafts until the owner signs off, `revalidateTag()` has no caller
until the Phase 8 admin writes exist, and the gallery is empty pending real photos.

---

## Phase 3 — Quote & order engine (4–5 days)

**Backend**
- [ ] `QuoteCalculator`: distinct-service counting, eligibility against `min_distinct_services`, integer-paise arithmetic.
- [ ] `DiscountAllocator` per `REQUIREMENTS.md` §8.3: exact proportional share → floor to paise → distribute leftover paise one at a time to the largest fractional remainders → deterministic tie-break on `order_item.id`. Property-based tests sweeping random baskets (service count, prices, quantities, discount percent) asserting **both** invariants: `SUM(discount_alloc_paise) == order.discount_paise` and `SUM(net_paid_paise) == order.total_paise`. Built in Phase 1 as a pure money util; wired to orders here.
- [ ] `POST /api/v1/orders/quote` with short-lived quote.
- [ ] `Order` + `OrderItem` models with snapshot fields and the `total = subtotal - discount` check constraint.
- [ ] `POST /api/v1/orders` — recalculates everything server-side, ignores any client-supplied money field.
- [ ] `Customer` model + get-or-create by phone.
- [ ] Order state machine with explicit legal transitions; illegal transitions raise.

**Frontend**
- [ ] Selection cart state (desktop panel / mobile sticky bar).
- [ ] Live quote call on selection change (debounced).
- [ ] `DiscountReveal` animation on the second distinct service, with an explanatory line.
- [ ] Checkout drawer form (name, phone, email) with React Hook Form + Zod.

**Tests:** discount boundary (1 vs 2 distinct services), quantity-of-same-service does *not* trigger the discount, rounding edges (₹0.01 cases), inactive/missing service rejection, **price-tampering attempt is ignored**.

**Done when:** a client request carrying a forged price produces an order at the correct server-side price.

---

## Phase 4 — Daily campaign & lucky engine (5–6 days) ⚠️ high risk

**Backend**
- [ ] `CampaignConfig` (append-only, `effective_from`) + `DailyCampaign` with unique `(salon_id, campaign_date)`.
- [ ] `LuckyEngine`:
  - 256-bit CSPRNG seed at campaign creation,
  - `commitment = SHA256(seed ‖ salon_id ‖ campaign_date ‖ capacity ‖ lucky_count)`,
  - deterministic uniform sampling of W unique positions from 1..N (seeded PRNG, no `random.randint` per payment),
  - seed and positions stored **encrypted**; commitment stored in clear.
- [ ] `CampaignProvisioner`: Beat task at 00:00 Asia/Kolkata **plus** lazy creation on first campaign-dependent request, both idempotent against the unique constraint.
- [ ] `SlotReservation` + `CapacityGuard` using `SELECT ... FOR UPDATE` on the campaign row; 10-minute TTL; expiry task.
- [ ] Config lock rule: `paid_count >= 1` → today immutable, edits become tomorrow's config.
- [ ] `GET /api/v1/promotion/today` returning **only** the safe aggregate metrics.
- [ ] Campaign closure task: close, expire reservations, finalise stats, preserve record permanently.

**Frontend**
- [ ] `CampaignProgressCard` with counters animating only after data arrives.
- [ ] "How It Works" 4-step section + promotion-rules link.
- [ ] "Slots full" state handling.

**Tests (the critical set):**
- [ ] Exactly W unique positions, all within 1..N, for hundreds of (N, W) combinations.
- [ ] Same seed + config reproduces the identical set; different seeds differ.
- [ ] Commitment verifies against the revealed seed after closure.
- [ ] **Concurrency:** `paid=39, capacity=40`, 20 simultaneous reservation requests → exactly one succeeds, count never exceeds 40.
- [ ] Duplicate campaign creation (scheduler + lazy path racing) → one row.
- [ ] No API response or serializer anywhere leaks winning positions (assert by scanning responses).

**Done when:** the concurrency test passes repeatedly under load, and a grep for winning-position fields across all serializers returns nothing.

---

## Phase 5 — Payments (6–8 days) ⚠️ high risk

**Backend**
- [ ] `PaymentGateway` abstract interface (`create_order`, `verify_client_payment`, `verify_webhook`, `fetch_payment`, `refund`).
- [ ] `RazorpayGateway` implementation; `CashfreeGateway` stub proving the abstraction holds.
- [ ] Secret manager integration; `PaymentGatewayConfig` storing references and masked key ID only.
- [ ] `POST /api/v1/payments/create` — amount read from `Order.total_paise`, reservation validated, order not already paid, returns only safe checkout config.
- [ ] `POST /api/v1/payments/verify` — recompute signature, verify amount + currency + gateway order ID, optional provider fetch, then mark verified.
- [ ] `POST /api/v1/webhooks/razorpay` — signature check → insert `(provider, gateway_event_id)` → duplicate returns 200 immediately → otherwise queue processing.
- [ ] Payment state machine + `reconcile_payments` task.
- [ ] `GET /api/v1/orders/{id}/status` for the abandoned-browser case.

**Frontend**
- [ ] Razorpay hosted/embedded checkout integration (no custom card form).
- [ ] `ProcessingStates` driven by real responses, with `aria-live`.
- [ ] Failure, cancellation and "payments temporarily unavailable" states.

**Tests:** success, failure, abandoned checkout, duplicate webhook ×3, webhook-before-verify, verify-before-webhook, delayed webhook, provider 5xx, amount mismatch, currency mismatch, unknown payment ID, forged signature, verify replay.

**Done when:** three identical `payment.captured` webhooks produce exactly one payment record, and a forged signature is rejected with nothing persisted.

---

## Phase 6 — Lucky result & coupons (4–5 days)

**Backend**
- [ ] The single atomic decision transaction: lock campaign row → verify not already processed → consume reservation → increment `paid_count` → `participant_number = paid_count` → membership check → create `LuckyDecision` → increment `winner_count` if winner → create `Coupon` + entitlements. One transaction, no exceptions.
- [ ] Unique constraints on `LuckyDecision.order_id` and `(daily_campaign_id, participant_number)` as the structural guard; the race loser reads and returns the existing decision.
- [ ] `CouponIssuer`: ≥128-bit opaque token, short human code, validity window, entitlement rows (`PAID` vs `FREE_REWARD`).
- [ ] `GET /api/v1/coupons/{token}` — customer-safe fields only, no gateway IDs, no internal IDs.
- [ ] QR generation carrying only the coupon URL.
- [ ] `CouponRedeemer` with `SELECT FOR UPDATE` + unique redemption row.
- [ ] Phone OTP flow (feature-flagged).
- [ ] Coupon expiry task.

**Frontend**
- [ ] `WinnerReveal` (short confetti, reward list, refund status) and `NonWinnerReveal` (accurate, shows savings, no fake near-win).
- [ ] `/coupon/[token]` page with QR, full detail, print/PDF/share.

**Tests:** simultaneous verify+webhook → one decision, one coupon; concurrent double scan → one redemption; expired/cancelled/redeemed states; invalid and randomly-guessed tokens; participant numbering under concurrent payments.

**Done when:** the verify-vs-webhook race test produces exactly one coupon across 100 runs.

---

## Phase 7 — Refunds (3–4 days)

Scope locked: **reward-attributable-only** (`REQUIREMENTS.md` §8.1).

- [ ] `RefundCalculator` — sum `net_paid_paise` across purchased lines whose service is in the campaign's reward package, minus already-refunded amount → `eligible_refund_paise`. Reward-package services **not** purchased → `free_service_entitlements`. Non-package lines are never refunded. Pure function, heavily unit-tested.
- [ ] `Refund` + `RefundAttempt` models, idempotency key, provider refund ID uniqueness.
- [ ] Refund creation inside the winner path; refund state machine.
- [ ] `retry_pending_refunds` with the 1m → 5m → 30m → 2h → `MANUAL_REVIEW_REQUIRED` ladder, full attempt trail.
- [ ] Refund status surfaced on the coupon page and the admin refund screen — **never hidden on failure**.

**Tests:** winner buying only reward services; winner buying reward + non-reward mix; discount allocation correctness; partial refund; provider failure then retry success; duplicate refund request; already-refunded.

**Done when:** for every basket shape, refund + retained amount reconciles exactly to the amount paid, to the paise.

---

## Phase 8 — Admin panel (8–10 days)

- [ ] Admin auth: login, TOTP MFA, server-side session cookies, throttling, lockout, step-up re-auth for sensitive actions.
- [ ] RBAC permission classes + the matrix from `REQUIREMENTS.md` §5, enforced at both API and UI layers.
- [ ] Dashboard with the eight KPI cards and the seven charts.
- [ ] Services admin: table, CRUD, reorder, image change, price dialog writing history.
- [ ] Campaign settings with the locked-today banner and effective-date control.
- [ ] Payment gateway screen: masked display, write-only secrets, Test Connection, MFA gate.
- [ ] Orders, Payments, Coupons, Refunds, Customers screens with the full filter sets.
- [ ] QR scanner screen for receptionists (camera → validate → redeem → confirmation → "already redeemed").
- [ ] Reports with async CSV/Excel export via Celery.
- [ ] Audit log viewer with masked before/after.
- [ ] Website content management (kept visually and structurally separate from financial config).
- [ ] Users & roles (OWNER only).
- [ ] `AuditWriter` wired to every sensitive action in the Doc 2 §38 list.

**Tests:** permission matrix per role per endpoint (table-driven), privilege escalation attempts, audit record written for every sensitive action, secrets never present in any admin API response.

**Done when:** a receptionist session cannot reach a single pricing, campaign or gateway endpoint, proven by test.

---

## Phase 9 — Security hardening (4–5 days)

- [ ] Security headers: HSTS, nonce-based CSP allowlisting Razorpay script/frame, nosniff, Referrer-Policy, Permissions-Policy.
- [ ] Cookie flags, CSRF on all cookie-auth mutations, explicit CORS allowlist.
- [ ] Rate limits per `REQUIREMENTS.md` §3.6, with Redis backing.
- [ ] Secrets fully migrated to the secret manager; repo history scanned for leaked secrets.
- [ ] Postgres locked to a private network, least-privilege app user, `AuditLog` with no UPDATE/DELETE grant.
- [ ] Log-exposure review: no secrets, CVV, PAN, UPI PIN, OTP or raw webhook bodies anywhere.
- [ ] Run the full Doc 2 §50 security checklist: SQLi, XSS, CSRF, CORS, auth bypass, IDOR, rate limits, coupon replay, duplicate webhook, last-slot concurrency, duplicate refund, double lucky processing, amount tampering, price tampering, privilege escalation.
- [ ] Dependency vulnerability scan wired into CI as a blocking step.

**Done when:** every item on the §50 checklist has a passing test or a written, accepted exception.

---

## Phase 10 — Production & launch (4–5 days)

- [ ] Staging environment mirroring production; smoke-test suite.
- [ ] Cloudflare: DNS, TLS, WAF rules, caching policy.
- [ ] Sentry, structured log aggregation, uptime checks.
- [ ] Alerts: webhook signature failure spike, refund failures over threshold, missing daily campaign, DB down, provider error spike, redemption endpoint failing, admin brute-force.
- [ ] Backups: daily DB backup, retention, offsite, encryption, **restore drill actually performed**.
- [ ] `reconcile_payments` verified against real gateway data in test mode.
- [ ] Runbooks written: gateway down, refund failures, DB issue, campaign init failure.
- [ ] Owner UAT — the 15 scenarios in Doc 3 §53, executed by the owner, not the developer.
- [ ] Legal pages published and signed off.
- [ ] Live Razorpay credentials added via the admin UI with MFA; live webhook registered and verified.
- [ ] Doc 3 §54 launch checklist completed item by item.
- [ ] Soft launch: low daily capacity for the first few days, watch metrics, then raise.

**Done when:** every box in the Doc 3 §54 checklist is ticked and a restore from backup has succeeded at least once.

---

## Definition of done (applies to every phase)

1. Unit tests for all domain logic; integration tests for all cross-boundary flows.
2. No money value ever touches a float.
3. Every sensitive action writes an audit record.
4. No secret in code, logs, API responses or Git history.
5. Migrations are additive and reversible, and CI's migration check passes.
6. New public UI is keyboard-navigable, contrast-compliant and reduced-motion-aware.
7. The Golden Backend Rule (Doc 2 §51) holds: for any order, the system can answer what was selected, at what price, why the discount applied, which campaign was active, what participant number was assigned, whether it won, which coupon was created, what was refunded, and who redeemed it.

---

## Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Capacity oversell under concurrent checkout | Promotional and financial exposure | Row-level lock + reservation TTL; concurrency test is a Phase 4 exit gate |
| Double coupon / double refund from the verify↔webhook race | Direct money loss | Unique constraints as the structural guard, not application `if` checks; Phase 6 exit gate |
| ~~Winner refund policy changed after build~~ | — | ✅ Resolved 2026-09-20: reward-attributable-only |
| Owner rejects "5 Lucky Slots" and demands 5 real winners daily | Phase 4/6 redesign to an end-of-day draw; immediate reveal lost | Escalate for sign-off **before Phase 4 starts**; Phases 1–3 are unaffected either way |
| Razorpay onboarding/KYC delay | Blocks Phase 5 | Start the account in Phase 0; build against the sandbox meanwhile |
| Winning positions leaked via an admin serializer | Campaign fairness destroyed | Encrypted at rest, excluded by an explicit denylist, response-scanning test in Phase 4 |
| Fewer participants than capacity → fewer than 5 winners | Marketing/legal complaint | "5 Lucky Slots" wording + promotion rules stating daily capacity behaviour (§8.2) |
| Scheduler outage leaves no campaign at 00:00 | Site cannot take orders | Lazy creation fallback on first request, idempotent via the unique constraint |
| Secrets committed to Git | Critical breach | Pre-commit secret scanner from Phase 1, CI scan, secret manager from Phase 5 |

---

## Immediate next actions — three parallel tracks

```
OWNER / BUSINESS                     EXTERNAL                    ENGINEERING
├─ Approve "5 Lucky Slots"           └─ Razorpay onboarding      └─ Phase 1 scaffolding
├─ Finalise promotion/refund rules      + test keys                 (no dependency on
└─ Answer §8.4 questions                + webhook URL                the other two tracks)
```

The first true engineering blocker arrives at **Phase 4** (needs the wording decision) and **Phase 5** (needs Razorpay keys). Phases 1–3 proceed regardless.
