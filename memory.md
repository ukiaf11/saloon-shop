# Project Memory — Salon Lucky Customer Platform

> Working memory for this project. Read this first at the start of a session; update it at the end of one.
> Keep it short and current — it is a state file, not a log archive. Details live in the docs it points to.

**Last updated:** 2026-09-20 (Phase 2 complete)

---

## 1. What this project is

A mobile-first single-page salon website plus a separate role-based admin panel.

Customer flow: pick services → automatic 10% discount for 2+ distinct services → pay by UPI/card (Razorpay) → immediately see whether they hit one of the day's pre-generated lucky slots → receive a QR coupon. Winners additionally get a refund of the reward-attributable amount and a free-service entitlement.

The hard requirement underneath all of it: **every money and promotion decision must be reproducible from persisted backend data.** The browser is never trusted with price, discount, lucky result, payment status or coupon validity.

---

## 2. Current state

| | |
|---|---|
| **Phase** | ✅ Phase 1 (foundation) and ✅ Phase 2 (catalog & content) complete. Phase 3 (quote & order engine) is next. |
| **Code** | `backend/` (Django 5 + DRF, uv-managed) and `frontend/` (Next 16, TS, Tailwind 4) both boot, migrate and pass their checks. Git repo initialised on `main`; nothing committed yet. |
| **Specs** | Three source documents (see §3). |
| **Derived docs** | `REQUIREMENTS.md`, `IMPLEMENTATION_PLAN.md`, `README.md`. |
| **Engineering blockers** | None until Phase 4 (needs the wording decision) and Phase 5 (needs Razorpay keys). |
| **Business track** | Owner to approve "5 Lucky Slots"; promotion/refund rules need drafting for legal. |

**Verified working:** `docker compose` Postgres + Redis, migrations, all three seed commands, `/healthz` + `/api/v1/readiness`, Celery round-trip, JSON log redaction, CORS allowlist, image upload validation (rejects disguised non-images and SVG), the six public read endpoints against the contract, the public page rendering real seeded data with full JSON-LD, the Next image optimizer on API-served media. **151 tests pass** (107 backend, 44 frontend); ruff + eslint + tsc + prettier + `check --deploy` all clean.

**Not yet measured:** Lighthouse mobile score (Phase 2 exit gate names it; needs a real device/CI run).

---

## 3. Document map

| File | What it holds |
|---|---|
| `01_PROJECT_BLUEPRINT_AND_ARCHITECTURE.md` | Vision, business rules, stack, entities, API groups, state machines, phases |
| `02_BACKEND_PAYMENT_LUCKY_ENGINE_SECURITY.md` | Transaction flows, payment integrity, lucky engine, refunds, security, testing |
| `03_FRONTEND_ADMIN_DEPLOYMENT_TESTING.md` | Public UI/UX, admin screens, deployment, monitoring, test strategy, launch checklist |
| `REQUIREMENTS.md` | Consolidated DB / backend / UI / infra / test requirements + open decisions |
| `IMPLEMENTATION_PLAN.md` | 11 phases with tasks, exit gates, estimates, risk register |

When the specs and the derived docs disagree, the three numbered source documents win.

---

## 4. Locked technical decisions

### Business (locked 2026-09-20)

- **Winner refund scope: reward-attributable-only.** Refund the `net_paid_paise` of purchased lines whose service is in the reward package. Non-package services stay paid. Package services not purchased become `FREE_REWARD` coupon entitlements. Worked example in `REQUIREMENTS.md` §8.1.
- **Discount allocation: largest-remainder, deterministic.** Exact proportional share → floor → distribute leftover paise to the largest fractional remainders → tie-break on `order_item.id` ascending. Two invariants asserted at write time and property-tested.
- **Marketing wording: "Har Din 5 Lucky Slots"** — recommended, awaiting owner sign-off. ⚠️ If the owner demands exactly 5 real winners daily, Phases 4 and 6 must be redesigned around an end-of-day draw and the immediate reveal is lost. Resolve before Phase 4.

### Technical

- **Frontend:** Next.js 16 App Router + TypeScript strict + Tailwind 4 (CSS `@theme` tokens, no JS config) + Motion; React Hook Form + Zod.
- **Backend:** Python 3.12 + Django 5 + DRF, dependencies managed by **uv** (`pyproject.toml` + `uv.lock`, `[dependency-groups] dev`). Not pip/requirements.txt.
- **DB:** PostgreSQL. **Cache/queue:** Redis. **Jobs:** Celery + Beat.
- **Payments:** Razorpay behind a `PaymentGateway` abstract interface (Cashfree stub proves the abstraction).
- **Admin:** custom Next.js app; Django admin disabled in production.
- **Money:** integer paise (`BIGINT`) everywhere. No floats in the money path, ever.
- **Time:** `TIMESTAMPTZ` in UTC; `campaign_date` is a `DATE` in `Asia/Kolkata`.
- **Lucky engine:** winning positions pre-generated from a 256-bit CSPRNG seed at campaign creation, seed + positions encrypted at rest, SHA256 commitment stored in clear. Never `random.randint` per payment.
- **Display formatting:** Indian digit grouping (₹12,34,567.89), implemented identically in `backend/common/money.py` and `frontend/src/lib/money.ts`.

---

## 5. Invariants — do not violate these

1. Frontend sends `service_ids` + contact fields only. The backend computes everything else.
2. Payment amount is read from `Order.total_paise`, never from a request body.
3. Capacity admission happens only inside `SELECT ... FOR UPDATE` on the `DailyCampaign` row.
4. Idempotency comes from **database unique constraints**, not application-level `if exists` checks.
5. The lucky decision, participant numbering, reservation consumption and coupon creation all happen in **one** transaction.
6. Winning positions never appear in any API response, serializer, log line or error message.
7. Today's campaign config becomes immutable the moment `paid_count >= 1`; edits become tomorrow's config.
8. `OrderItem` snapshots (`service_name_snapshot`, `unit_price_paise`, `line_total_paise`) are mandatory — a later price change must not rewrite past orders.
9. Coupon URLs use an opaque ≥128-bit token. No sequential IDs, no PII in the QR payload.
10. Gateway secrets live in a secret manager; the DB stores references and a masked key ID only.
11. `AuditLog` is append-only; the application DB user has no UPDATE/DELETE grant on it.
12. Never log: gateway secrets, CVV, card numbers, UPI PIN, OTP, raw webhook payloads.

---

## 6. Open questions

Full list with working assumptions: `REQUIREMENTS.md` §8.4. None block engineering before Phase 4.

**The one that still matters:** owner sign-off on **"5 Lucky Slots"** wording. It is the only open item that could force an architecture change (end-of-day draw instead of immediate reveal). Everything else — email required?, OTP before payment?, coupon validity, hosting target, GST — has a working assumption and can be changed cheaply later.

---

## 7. Known traps in this domain

- **Fewer participants than capacity means fewer than 5 winners.** Positions `[4, 11, 18, 29, 37]` with only 20 customers yields 3 winners, not 5. This is inherent to the pre-generated-positions design (chosen because the customer must see an immediate result). The marketing wording must accommodate it.
- **The verify ↔ webhook race is the default case, not an edge case.** Both paths will regularly try to finalise the same order. Design for the loser reading the winner's result.
- **Quantity of the same service does not unlock the discount** — only distinct services count.
- **Discount allocation must round to an exact sum.** Per-line allocations have to add up to `discount_paise` to the paise, or refunds will not reconcile. Use largest-remainder.
- **Never rely on the scheduler alone** for daily campaign creation — the lazy fallback path is required, and both paths must be idempotent against `UNIQUE (salon_id, campaign_date)`.

---

## 8. Session log

| Date | What happened |
|---|---|
| 2026-09-20 | Read all three specs. Wrote `REQUIREMENTS.md` (DB schema across 11 app domains, backend services/API/jobs/security, public + admin UI, infra, tests, open decisions) and `IMPLEMENTATION_PLAN.md` (11 phases, ~46–58 dev-days, exit gates, risk register). |
| 2026-09-20 | Owner locked refund scope (reward-attributable-only) and discount allocation (largest-remainder). Docs updated. **Phase 1 built and verified**. Backend switched from pip/venv to **uv** at the owner's request. |
| 2026-09-20 | **Phase 2 built and verified** via a 5-agent parallel fan-out (catalog app, content app, salon API, frontend data layer, frontend sections) over disjoint file ownership, with central wiring, migrations and integration fixes done afterwards. Local `git init` from Phase 1 was **removed** at the user's request — nothing was ever committed. See §10. |

---

## 9. What Phase 1 built

```
backend/                     Django 5 + DRF, uv-managed (pyproject.toml + uv.lock)
  config/settings/           base / local / staging / production split
  config/celery.py           Beat schedule for all 5 recurring tasks
  common/money.py            integer-paise arithmetic + largest-remainder allocator
  common/masking.py          redaction denylist (secrets, PAN, OTP, winning positions)
  common/logging.py          JSON formatter; redacts extras before serialising
  common/middleware.py       request_id (validates inbound UUID, echoes header)
  common/exceptions.py       DomainError hierarchy + uniform API error envelope
  common/locks.py            select_for_update helper; refuses outside a transaction
  common/tokens.py           opaque coupon tokens, human codes, numeric OTP
  apps/                      12 app skeletons; salons + accounts have models
  tasks/                     6 Celery task modules, stubbed with real names
  tests/test_money.py        13 tests incl. property-based (900+ generated baskets)

frontend/                    Next 16 App Router, TS strict, Tailwind 4
  src/app/globals.css        @theme design tokens, focus-visible, reduced-motion
  src/lib/api.ts             typed client, Zod-validated, ApiError with stable codes
  src/lib/money.ts           display-only INR formatting (Indian grouping)
  src/types/api.ts           response schemas mirroring backend serializers
  src/components/layout/     navbar (mobile menu) + footer
  src/app/{5 legal routes}   shells; robots.ts excludes /admin and /coupon/

docker-compose.yml           6 services, configurable host ports
.github/workflows/ci.yml     backend + frontend + security + docker jobs
.pre-commit-config.yaml      gitleaks, ruff, private-key detection
```

## 10. What Phase 2 built

```
backend/apps/catalog/      Service, ServiceCategory, ServicePriceHistory
                           services.py: change_service_price() is the ONLY sanctioned
                           price path; Service.save() raises PriceChangeNotAudited
                           otherwise, so history cannot be silently skipped
backend/apps/content/      SiteContent, GalleryImage, Testimonial, FaqItem,
                           versioned append-only LegalPage + publish_legal_page()
backend/apps/salons/       public GET /salon: always 7 business-hour rows, SiteContent
                           merged over documented defaults, blank -> null normalisation
backend/common/cache.py    cached()/invalidate() + the KEY_* registry (written centrally
                           so all three apps share one caching approach)
backend/common/images.py   upload validation by BYTES, not extension or content-type

frontend/src/types/api.ts        Zod schemas for all six endpoints
frontend/src/lib/site-data.ts    server readers, tagged + revalidating, degrade on outage
frontend/src/lib/structured-data.ts  LocalBusiness / Service / FAQPage JSON-LD
frontend/src/components/sections/    9 sections, all Server Components, zero "use client"
frontend/src/components/legal/       markdown legal pages (react-markdown, no raw HTML)
```

**Public endpoints live:** `/salon`, `/services`, `/gallery`, `/testimonials`, `/faqs`, `/legal/{slug}`.

### Phase 2 decisions worth remembering

- **Price changes are structurally guarded**, not merely by convention: `Service.save()` rejects an unaudited price change. If a future phase needs a bulk price update, it must go through `change_service_price()` or explicitly set the sanctioned flag.
- **Cache invalidation is explicit + on-commit.** TTL is only a backstop. Signals cover Service, ServiceCategory, GalleryImage, Testimonial, FaqItem, SiteContent, Salon and BusinessHour.
- **Next fetch caching needs the tag, not just the window.** Without `tags`, Next cached the public reads persistently and an owner's price edit would never reach the page — observed for real during the build. `CACHE_TAGS` in `site-data.ts` is what the Phase 8 admin save path must call `revalidateTag()` with.
- **`dangerouslyAllowLocalIP` is development-only.** Next 16 refuses to optimize images resolving to private IPs (an SSRF guard). The guard stays on in production, where media comes from object storage.
- **Legal pages render Markdown with raw HTML disabled.** Do not add `rehype-raw` — these are the binding promotion and refund terms.

### Phase 2 was adversarially reviewed

A 6-dimension review (contract, money-audit, caching, security, frontend-runtime,
data-model) raised 24 findings; 3-vote adversarial verification confirmed 5 and
refuted 19. All 5 are fixed:

1. **Skip link invisible on focus** (high, a11y). A hand-written `.sr-only` in
   `globals.css` sat *outside* any cascade layer, so it beat Tailwind v4's
   layered `focus:not-sr-only` reset and left the first tab stop clipped to 1x1.
   Fixed by deleting the duplicate — Tailwind's own `.sr-only` uses `clip-path`,
   which the reset does undo. Verified in headless Chrome: focused 146x40 with a
   gold background and focus ring, blurred 1x1.
   **Do not re-add a hand-written `.sr-only`**, and if one is ever needed it must
   live in `@layer utilities` and use `clip-path: inset(50%)`, never legacy `clip`.
2. **Tests flushed the dev Redis.** `cache.clear()` against the configured Redis
   is a FLUSHDB of db 0 — also the Celery broker — so running the suite with the
   stack up silently deleted queued tasks. Fixed with an autouse fixture in
   `backend/conftest.py` forcing every test onto locmem; verified by seeding a
   sentinel key and a queue entry and confirming both survive a full run.
3. **Location section rendered an empty bordered card** when every contact field
   was null (the current seeded state). Now shows an honest fallback line.
4. **Legal Markdown could not render tables.** `react-markdown` had no
   `remark-gfm`, so a pipe table in the binding promotion rules would render as
   run-on `|` characters. Added; verified real `<table>`/`<del>` output.
5. **`#contact` anchor vanished when /salon was unreachable**, dead-linking the
   navbar. The section now always renders and handles its own empty state.
   The same finding exposed a fragile `socialLinksSchema` requiring *both*
   `instagram` and `facebook`: an owner saving only one would fail the whole
   /salon parse and blank the hours, contact and why-us sections. Now tolerant.

**XSS posture verified independently**, not merely reviewed: hostile CMS content
(`</script><script>`, `<img onerror>`) injected into a testimonial and an FAQ,
then checked in a real browser — nothing executed, `</script>` escaped to
`\u003c/script\u003e` inside JSON-LD, markup rendered as inert text.

### Latent issues the review refuted for now — revisit in Phase 8

These were correctly judged unreachable *today*, but the admin write paths in
Phase 8 are exactly what makes them reachable:

- `/services` is not scoped to a salon or to salon status (fine at one salon;
  breaks at multi-branch).
- `ServicePriceHistory.service` is `on_delete=CASCADE`, so deleting a Service
  would destroy its price audit trail. Nothing deletes services today.
- `GalleryImage.save()` only measures `width`/`height` when they are `None`, so
  replacing an image leaves stale dimensions.
- `LegalPage` has no cache-invalidation signal; only `publish_legal_page()`
  invalidates. An admin write bypassing the service layer would serve a stale page.
- The price guard compares against an in-memory snapshot, so `queryset.update()`,
  `bulk_update()` and `.only()`/`.defer()` loads can still bypass history.

### Known gaps carried into Phase 3+

- Legal pages are seeded as **drafts** and 404 until real copy is published — blocked on the owner's legal sign-off.
- `revalidateTag()` is not called anywhere yet; the admin write paths that must call it arrive in Phase 8.
- Gallery is empty (no real photos supplied yet), so the gallery section renders nothing.
- A build run while the API is down exits 0 and ships empty sections; the 5-minute revalidate window self-heals it. CI builds with no backend, so this tolerance is required.
- Lighthouse mobile not yet measured.

## 11. Next actions

**Engineering — start Phase 3 (quote & order engine):** `QuoteCalculator` and the
`DiscountAllocator` (the allocator already exists and is property-tested in
`common/money.py` — wire it to real orders); `Order`/`OrderItem` with snapshot
fields and `net_paid_paise`; `POST /orders/quote` and `POST /orders`; the
selection cart, live quote and discount-reveal animation on the frontend.
Exit gate: a forged client price must produce an order at the correct server price.

**Business — unblock Phase 4:** get the "5 Lucky Slots" wording signed off.

**External — unblock Phase 5:** Razorpay onboarding, test keys, webhook URL.

**Housekeeping:** the repo is **not** a git repo — the user will supply GitHub
credentials and ask for that work explicitly. Do not `git init`, commit or push
until then. When that happens, run `pre-commit install` first so gitleaks guards
history from the very first commit.
