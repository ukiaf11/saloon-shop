# Project Memory — Salon Lucky Customer Platform

> Working memory for this project. Read this first at the start of a session; update it at the end of one.
> Keep it short and current — it is a state file, not a log archive. Details live in the docs it points to.

**Last updated:** 2026-09-21 (Phase 4 complete; claymorphism redesign; **live on Vercel**)

---

## 1. What this project is

A mobile-first single-page salon website plus a separate role-based admin panel.

Customer flow: pick services → automatic 10% discount for 2+ distinct services → pay by UPI/card (Razorpay) → immediately see whether they hit one of the day's pre-generated lucky slots → receive a QR coupon. Winners additionally get a refund of the reward-attributable amount and a free-service entitlement.

The hard requirement underneath all of it: **every money and promotion decision must be reproducible from persisted backend data.** The browser is never trusted with price, discount, lucky result, payment status or coupon validity.

---

## 2. Current state

| | |
|---|---|
| **Phase** | ✅ Phases 1–4 complete. Phase 5 (payments) is next — **blocked on Razorpay test keys**. |
| **Code** | `backend/` (Django 5 + DRF, uv-managed) and `frontend/` (Next 16, TS, Tailwind 4) both boot, migrate and pass their checks. |
| **Repo** | <https://github.com/ukiaf11/saloon-shop> (**public**), branch `main`. CI and container images green; Pages is now manual-only. |
| **Live** | <https://saloon-shop-web.vercel.app> + <https://saloon-shop-api.vercel.app> on Vercel Hobby with Neon, Singapore. noindex. See §16. |
| **Specs** | Three source documents (see §3). |
| **Derived docs** | `REQUIREMENTS.md`, `IMPLEMENTATION_PLAN.md`, `README.md`. |
| **Engineering blockers** | None until Phase 4 (needs the wording decision) and Phase 5 (needs Razorpay keys). |
| **Business track** | Owner to approve "5 Lucky Slots"; promotion/refund rules need drafting for legal. |

**Verified working:** `docker compose` Postgres + Redis, migrations, all three seed commands, `/healthz` + `/api/v1/readiness`, Celery round-trip, JSON log redaction, CORS allowlist, image upload validation (rejects disguised non-images and SVG), the six public read endpoints against the contract, the public page rendering real seeded data with full JSON-LD, the Next image optimizer on API-served media. **301 tests pass** (243 backend, 58 frontend); ruff + eslint + tsc + prettier + `check --deploy` all clean.

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

## 11. What Phase 3 built

```
backend/apps/promotions/  CampaignConfig (append-only, effective_from) +
                          config_for(salon, date) -- reading the newest row
                          directly would use tomorrow's settings on today's order
backend/apps/customers/   Customer + normalise_phone (E.164, assumes +91 for a
                          bare 10-digit entry) so one person is never two rows
backend/apps/orders/      state.py  -- the full transition table; illegal and
                                       no-op transitions both raise
                          services.py -- build_quote / create_order
                          models   -- Order, OrderItem with snapshot columns and
                                      DB-level CHECKs on the arithmetic
frontend/src/lib/cart.tsx     selection state; holds NO money
frontend/src/lib/use-quote.ts debounced, aborts superseded requests, derives
                              "loading" so a stale total never shows
frontend/src/components/cart/, checkout/  sticky bar, discount reveal, drawer
```

**Scope deviation:** `CampaignConfig` was built in Phase 3, not Phase 4 — a quote
needs `discount_percent` and `min_distinct_services`. Phase 4 adds only
`DailyCampaign`, `SlotReservation`, the lucky engine, and the
`Order.daily_campaign` FK (left out deliberately, as an additive migration).

### Phase 3 decisions worth remembering

- **The request serializers have no price fields at all.** A forged price is not
  rejected, it is unbindable. Verified over real HTTP.
- **`discount_percent` vs `configured_discount_percent`.** The first is what was
  *applied* (0 when ineligible, so the UI can never show a discount that was not
  given); the second is the campaign rate, so the UI can say "add 1 more service
  to unlock 10% off" without implying it is already on the total.
- **Public order numbers are `SL-YYMMDD-XXXX` with a random suffix.** Sequential
  numbers would tell every customer the salon's order volume.
- **Idempotency is a request header**, reused across retries of one checkout
  attempt; the drawer is mounted per-attempt so each gets a fresh key.
- **Quantity does not unlock the discount.** Only distinct services count.

### Two integration bugs the browser test caught (unit tests could not)

Both were CORS, and both only appear in a real browser:

1. `CORS_ALLOWED_ORIGINS` listed `localhost:3000` but not `127.0.0.1:3000`. A dev
   using the other spelling gets silently failing quotes. Both are allowlisted now.
2. `POST /orders` sends an `Idempotency-Key` header, which is **not** in
   django-cors-headers' default allowlist, so the browser rejected the preflight
   and the call never left the page — while the quote, which sends no such
   header, worked fine. `CORS_ALLOW_HEADERS` now includes it.

The lesson worth keeping: any new custom request header needs a
`CORS_ALLOW_HEADERS` entry, or it fails only in the browser.

## 12. What Phase 4 built

```
backend/common/crypto.py       Fernet field encryption. Production REFUSES to
                               run without FIELD_ENCRYPTION_KEY; DEBUG derives
                               one from SECRET_KEY for convenience.
backend/apps/promotions/
  lucky.py                     seed -> commitment -> positions. Pure, no ORM.
  models.py                    DailyCampaign (the lock anchor), SlotReservation
  services.py                  provision_campaign, reserve_slot, close_campaign,
                               public_progress (the allowlist)
  views.py/urls.py             GET /promotion/today
tasks/campaigns.py             midnight rollover + reservation expiry
tests/test_no_secret_leaks.py  static guard over every serializer and view
frontend/src/components/sections/campaign.tsx  live counters, polled
```

### The decisions that matter

- **HMAC-SHA256 ordering, not `random.sample`.** Positions are chosen by sorting
  1..N on `HMAC(seed, i)`. `random.sample` is seeded-deterministic but its
  algorithm is a CPython implementation detail — a Python upgrade could silently
  make every past campaign unverifiable. HMAC is specified, stable forever, and
  an auditor can re-derive any day in ten lines of any language.
- **The commitment binds every parameter** (seed, salon, date, capacity,
  lucky_count). Without that, someone could later claim the same seed was drawn
  for a different capacity — which would mean different positions.
- **`seed_commitment` is exempt from log redaction** (`common/masking.py`
  `PUBLIC_KEY_EXCEPTIONS`). It is a hash published precisely so results can be
  verified; redacting it made the audit trail useless for no security gain.
  Keep that exception list tiny.
- **Capacity counts `paid_count + live reservations`** under a
  `SELECT ... FOR UPDATE` on the campaign row. Counting paid alone would promise
  the last slot to everyone still paying for it.
- **Provisioning is idempotent by unique constraint, not by checking first.**
  The midnight task and the first visitor of the day *will* race; one INSERT
  wins and the loser re-reads.
- **`/promotion/today` is not cached** on either side. A stale count makes a
  customer believe a slot is free when it is not.

### Exit gates, both passing

- 20 threads racing for the last slot → exactly 1 admitted. 30 threads against
  10 slots → exactly 10. 12 threads provisioning → 1 campaign row.
- `tests/test_no_secret_leaks.py` scans serializers and views for the secret
  fields, pins down who may call `decrypt_winning_positions`, and asserts the
  view cannot build its own payload around `public_progress`.

### The bug CI caught that local runs hid

pytest-django forces `settings.DEBUG = False` during tests, so `common/crypto.py`
takes its production branch and demands a real key. Locally the suite passed
only because a `.env` file happened to exist on disk — django-environ reads that
file regardless of the process environment. CI has no `.env`, so every
campaign test 500'd.

Fixed by giving the suite its own key in `backend/conftest.py`, the same way the
cache is isolated there. **Tests must not depend on ambient config.** Verified
by deleting `.env` entirely and re-running: 231 pass.

### Carried into Phase 6

`decrypt_winning_positions()` currently has no caller. Phase 6's lucky decision
will be the first, and `tests/test_no_secret_leaks.py` must be updated to allow
it — deliberately, so adding a caller is a conscious act.

## 13. Claymorphism redesign, images, mobile (2026-09-21)

### Design system (`frontend/src/app/globals.css`)
Warm clay palette, dual inner shadow + soft drop shadow, generous radii. Utilities:
`clay`, `clay-sm`, `clay-well` (pressed-in), `clay-btn`, `clay-btn-soft`.
Fonts: **Fraunces with its SOFT axis at 100** (rounded serif) + **Nunito**.
**Every text/background pairing was measured to WCAG AA before use** — clay
palettes drift into pastel-on-cream easily; re-measure before adding a colour.

### Images
- **Illustrations** (`components/clay/clay-art.tsx`): original SVG clay art, one
  per service slug plus step/trust icons. Unknown slugs fall back to a comb.
- **Photos**: 3 CC BY 2.0 images by Nenad Stojkovic via Wikimedia Commons,
  in `src/assets/photos/`, credited on-image and at `/credits`
  (generated from `credits.json`). Two candidates were rejected: one dated and
  off-brand, one with an identifiable customer's face.
- **Photos are IMPORTED, not referenced by path.** A string src is not prefixed
  with basePath when images are unoptimized, so on GitHub Pages every photo
  404'd. Imports get basePath, content hashing and blur placeholders.

### Honesty decisions — do not undo
- **Seeded testimonials are unpublished.** They were invented in Phase 2;
  fake reviews on a real business's site mislead customers. A test pins this.
- **Gallery renders nothing until the owner uploads real photos** — stock
  photography must not be passed off as this salon.
- Preview-mode copy says the lucky draw runs on **paid online bookings** — an
  earlier draft wrongly implied walk-ins entered it.

### Mobile (measured at 360/390/430/768px)
Zero horizontal scroll; zero text under 12px; tap targets 44px (steppers 40px);
all inputs 16px so iOS Safari does not zoom; phone field opens the numeric
keypad; checkout sheet fits the viewport and locks background scroll. Services
and how-it-works are compact horizontal rows on phones. Hero shows 2 badges on
phones (3 covered the photo credit). Scripts that measured all this live in the
session scratchpad, not the repo.

### GitHub Pages now shows real data
`pages.yml` runs Postgres + Redis + the real Django API **inside the build
job**, seeds it, and exports against it. Guard: the job fails if the export has
no services. Two URLs, deliberately:
- `API_INTERNAL_URL` — server-only, never inlined; used at build/SSR time.
- `NEXT_PUBLIC_API_BASE_URL` — what the **browser** calls. With a single URL the
  Pages bundle pointed every visitor's browser at its own localhost.
With no public API configured, `NEXT_PUBLIC_BOOKING_ENABLED=0`: Add becomes
"Book in salon", the cart tray and campaign poll stand down (a stale cart in
localStorage is guarded too).

### Railway — superseded by Vercel
Railway refused provisioning ("Free plan resource provision limit exceeded"),
and the user then chose Vercel. The Railway files were removed in b01bd2a. Two
fixes from that work remain and are still worth having: **throttling fails
open** when the cache is down (a Redis blip used to 500 the whole API), and
`/healthz` is exempt from the HTTPS redirect.

## 14. Next actions

**Engineering — Phase 5 (payments), blocked on Razorpay test keys.** Provider
abstraction, `PaymentGatewayConfig` storing secret *references* only, payment
create/verify, the webhook with `UNIQUE (provider, gateway_event_id)` as the
idempotency mechanism, and the reconciliation job. Exit gate: three identical
`payment.captured` webhooks produce exactly one payment record.

Phase 3 and 4 left two seams Phase 5 must connect: an order is created but
nothing reserves a slot for it yet, and `Order.daily_campaign` is never
populated. Reserving at payment-create time (not order-create) is the right
place — a hold taken before the customer commits would burn capacity on
abandoned baskets.

✅ **Resolved 2026-09-21:** the owner confirmed **"5 Lucky Slots" with immediate
reveal**. The end-of-day-draw alternative is off the table.

**Business — unblock Phase 4:** get the "5 Lucky Slots" wording signed off.

**External — unblock Phase 5:** Razorpay onboarding, test keys, webhook URL.

**Before launch (hosting):** Vercel **Pro** (Hobby is non-commercial, and
Phase 5 needs per-minute cron), a custom domain, object storage for media, a
real owner account (the seeded `owner@example.com` is a placeholder), real
salon content, and approved legal copy.

**Housekeeping:** `pre-commit install` has not been run locally yet — do it so
gitleaks guards commits before they leave the machine (CI scans too, but that is
after the fact).

## 15. Repo, CI and deployment

**Repo:** <https://github.com/ukiaf11/saloon-shop>, public, `main`.

Pushes use an ephemeral credential helper, never a token in the remote URL or
`.git/config`:

```bash
export GH_USER=ukiaf11 GH_TOKEN=<pat>
git -c credential.helper='!f() { echo "username=$GH_USER"; echo "password=$GH_TOKEN"; }; f' push origin main
```

**Before every push:** stage, then scan the staged *content* for real secret
values, not just filenames. `.env`, `backend/.env` and `frontend/.env.local` all
hold live secrets and are gitignored; `.env.example` templates are committed and
must stay valueless.

**Three workflows:**

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | PR + `main` | ruff/format/migration-check/pytest (Postgres+Redis services), eslint/tsc/prettier/vitest/build, gitleaks + pip-audit + npm audit, Docker builds |
| `cd-images.yml` | `main`, tags | Builds both prod images to GHCR tagged `latest`/`main`/`sha-…`; smoke-tests the backend with `check --deploy` |
| `pages.yml` | manual only | Static export to <https://ukiaf11.github.io/saloon-shop/> (the fallback, now that Vercel is live) |

**The Pages deploy is a preview, not the product.** Pages runs no Node and no
Django, so: no API behind it, content frozen at build time (empty if no API was
reachable), no `revalidateTag`, no image optimizer, no `next.config.ts` headers,
and checkout/campaign/coupons/admin cannot work at all. It is **noindex by
default** so a site that cannot take a booking never outranks the real one.
Repo variables `PUBLIC_API_BASE_URL`, `PUBLIC_MEDIA_HOSTNAME` and
`PAGES_ALLOW_INDEXING` control that.

**Two bugs the first Pages run exposed, both fixed and worth remembering:**

- `API_BASE_URL` used `??`, but an unset GitHub Actions variable arrives as an
  empty string, not `undefined`, so the localhost fallback never fired and every
  request URL went relative. Blank now counts as unset.
- The site-data readers are documented to degrade when the API is down, but had
  no timeout, so they could not — they hung until the framework's 60s per-page
  build timeout fired on every retry. `apiRequest` now takes `timeoutMs`
  (10s default, 6s for build-time reads), combined with any caller signal.

**Static export requires** `export const dynamic = "force-static"` on
`robots.ts` and `sitemap.ts`, `images.unoptimized`, `trailingSlash`, and a
`basePath` of `/<repo>` for a project page.

## 16. Vercel deployment (live 2026-09-21)

| Resource | Id / name | Notes |
|---|---|---|
| Team | `team_o0FjGZjNtmWvLc4iggJ32lgj` (upendras-projects-34931334) | Hobby plan. Also holds unrelated `hotel-web` projects; leave them alone |
| API project | `saloon-shop-api` `prj_tVLVDzff9YtJ0e0fT78Fe3kZ4Lkv` | framework `django`, root `backend`, `sin1`, 30s max duration |
| Web project | `saloon-shop-web` `prj_u7AMQDyMDCbGxh70MJQ9RX5CNeNr` | framework `nextjs`, root `frontend`, `sin1` |
| Database | Neon store `saloon-db` `store_HNHNxfv1ChZLh0op` (Neon `cool-sound-64875082`) | Singapore, connected to the API project for production only |
| Unused | Neon store `neon-violet-canvas` (iad1) | Created by the user before the region decision. Safe to delete |

**How it runs.** Both projects are linked to `ukiaf11/saloon-shop`, and every
push to `main` redeploys both. The backend skips preview builds
(`ignoreCommand`) because a preview would migrate the production database. A
production build runs `backend/vercel_build.py`, which does `migrate` and
`createcachetable` against `DATABASE_URL_UNPOOLED`. The cache is the database
cache; there is no Redis. There is also no Celery. The only scheduled job is the
Vercel Cron `0 19 * * *` UTC calling `common/cron.py`.

**Verified live:** healthz, readiness (db + cache), catalog, today's campaign,
the cron gate (401 without the secret, 200 with it), CORS both ways, the
Idempotency-Key preflight, HSTS, no debug pages, and robots/meta noindex. Also
tested in real Chrome: add two services, cross-origin quote gives ₹450 − ₹45 =
₹405, checkout sheet opens, zero console errors, no horizontal scroll at 390px.

**Verified, not just assumed: cron gets through Deployment Protection.**
Vercel calls the cron on the *deployment* URL
(`saloon-shop-<hash>-….vercel.app`). Anonymous requests to that URL get a 302
to the Vercel login page. A `vercel crons run` still reached Django, passed the
`CRON_SECRET` check and logged `daily_campaign_rollover`. `VERCEL_URL` is in
`ALLOWED_HOSTS` for exactly this reason.

**Traps hit, so they are not hit again:**
- Vercel's Django preset serves **ASGI whenever `ASGI_APPLICATION` is set**, so
  it was removed; the app is WSGI.
- `config/__init__` imports Celery before `wsgi.py` runs, so `config/celery.py`
  has to default `DJANGO_SETTINGS_MODULE` to production.
- `[tool.uv] package = false` is required, or `uv sync` tries to build the
  project as a package. It changed exactly one `uv.lock` line
  (`editable` → `virtual`).
- A user token cannot call `/v1/installations/{id}/resources` (403). The CLI's
  route works: `POST /v1/storage/stores/{storeId}/connections`.
- Creating a project does not trigger a build. The first deploy has to be
  `POST /v13/deployments` with a `gitSource`.
- Neon behind PgBouncer (transaction mode) needs `CONN_MAX_AGE=0` and
  `DISABLE_SERVER_SIDE_CURSORS=True`.
- Historical logs: `vercel logs --since 3h --json`. The REST runtime-logs
  endpoint only streams new lines.
- To run the Vercel CLI without exposing the token, set `VERCEL_TOKEN` in the
  environment, use a scratch `.vercel/project.json` with `projectId` and
  `orgId`, and pass `-Q <scratch dir>`.

**Env vars (names only; values live in Vercel and the root `.env`).** API:
`DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`,
`CRON_SECRET`, `PAYMENT_GATEWAY_MODE=test`, `DJANGO_ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, plus 16 injected by Neon. The
one-off `SEED_*` vars were **deleted** after the first build. Web:
`NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SITE_URL`,
`NEXT_PUBLIC_BOOKING_ENABLED=1`, `NEXT_PUBLIC_NOINDEX=1`. Changing a
`NEXT_PUBLIC_*` value needs a **rebuild**, because it is inlined at build time.

**Rotating `FIELD_ENCRYPTION_KEY` makes stored lucky seeds unreadable.** Do not
change it without a re-encryption migration.
