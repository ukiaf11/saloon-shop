# Salon Lucky Customer Platform

[![CI](https://github.com/ukiaf11/saloon-shop/actions/workflows/ci.yml/badge.svg)](https://github.com/ukiaf11/saloon-shop/actions/workflows/ci.yml)
[![Images](https://github.com/ukiaf11/saloon-shop/actions/workflows/cd-images.yml/badge.svg)](https://github.com/ukiaf11/saloon-shop/actions/workflows/cd-images.yml)
[![Pages](https://github.com/ukiaf11/saloon-shop/actions/workflows/pages.yml/badge.svg)](https://github.com/ukiaf11/saloon-shop/actions/workflows/pages.yml)

Mobile-first salon website with a daily lucky-slot campaign, online payment, QR
coupons and a role-based admin panel.

**Status:** Phases 1–4 complete (foundation; catalog & content; quote & orders; daily campaign & lucky engine), plus a **UPI QR payment fallback** with an owner panel: customers pay the salon's own QR, the owner confirms each payment, and confirmation runs the daily draw. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

**Live (Vercel, noindex until launch):** site <https://saloon-shop-web.vercel.app> · API <https://saloon-shop-api.vercel.app/api/v1/services>

| Document | Contents |
|---|---|
| [memory.md](memory.md) | Project state, invariants, open questions — **read this first** |
| [REQUIREMENTS.md](REQUIREMENTS.md) | DB / backend / UI / infra requirements, locked decisions |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Phased build plan with exit gates |
| `01_`–`03_*.md` | Original specifications (authoritative on any disagreement) |

## Stack

- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind 4, Motion, Zod
- **Backend:** Django 5 + DRF, managed with [uv](https://docs.astral.sh/uv/)
- **Data:** PostgreSQL 16, Redis 7, Celery + Beat
- **Payments:** Razorpay behind a provider-agnostic gateway interface

## Quick start

### With Docker (everything)

```bash
cp .env.example .env                      # host port overrides, if needed
cp backend/.env.example backend/.env      # fill DJANGO_SECRET_KEY
cp frontend/.env.example frontend/.env.local
docker compose up
```

Frontend on http://localhost:3000, API on http://localhost:8000.

> If a Postgres is already running on 5432, set `POSTGRES_HOST_PORT=5433` in the
> root `.env` and point `DATABASE_URL` at it.

### Backend only

```bash
cd backend
uv sync                                   # creates .venv from uv.lock
uv run python manage.py migrate
SEED_OWNER_PASSWORD='<12+ chars>' uv run python manage.py seed_salon
uv run python manage.py seed_catalog
uv run python manage.py seed_content
uv run python manage.py runserver
```

### Frontend only

```bash
cd frontend
npm ci
npm run dev
```

## Checks

```bash
# backend
cd backend
uv run ruff check . && uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run
uv run pytest -q

# frontend
cd frontend
npm run lint && npm run typecheck && npm run format:check && npm run test
```

CI runs all of the above plus a secret scan, dependency audits and Docker image
builds.

## Endpoints

| Path | Purpose |
|---|---|
| `GET /healthz` | Liveness — no dependencies, for the load balancer |
| `GET /api/v1/readiness` | Readiness — checks the database and the cache |
| `GET /api/v1/salon` | Salon profile, 7-day business hours, CMS content |
| `GET /api/v1/services` | Active services + categories |
| `GET /api/v1/gallery` | Gallery images |
| `GET /api/v1/testimonials` | Published testimonials |
| `GET /api/v1/faqs` | Published FAQs |
| `GET /api/v1/legal/{slug}` | Latest published legal page (terms / privacy / refunds / promotion-rules) |
| `POST /api/v1/orders/quote` | Server-side pricing preview (advisory) |
| `POST /api/v1/orders` | Create an order with snapshotted prices |
| `GET /api/v1/orders/{id}` | Recover an order by its unguessable id |
| `GET /api/v1/promotion/today` | Live campaign counters (safe aggregates only) |
| `GET /api/v1/payments/options` | How customers can pay right now (`upi_qr` / `gateway` / `unavailable`) |
| `GET /api/v1/payments/qr-image` | The salon's UPI QR, re-encoded PNG |
| `POST /api/v1/orders/{id}/upi-payment` | Customer submits their 12-digit UPI reference (a claim, not a payment) |
| `POST /api/v1/auth/login` · `logout` · `me` · `password` | Owner sign-in (bearer token) |
| `/api/v1/owner/payment-settings` | Owner: QR image, UPI ID, name (password re-entered on every change) |
| `/api/v1/owner/payments` · `…/{id}/confirm` · `…/{id}/reject` | Owner: check claims; confirming marks paid and decides the draw |
| `/api/v1/owner/refunds` · `…/{id}/mark-sent` | Owner: winners' refunds, sent by UPI or cash and recorded here |

Photo credits: [`/credits`](<frontend/src/app/(site)/credits/page.tsx>), generated from `frontend/src/assets/photos/credits.json`.

Response shapes are fixed by [API_CONTRACT_PHASE2.md](API_CONTRACT_PHASE2.md),
[API_CONTRACT_PHASE3.md](API_CONTRACT_PHASE3.md) and
[API_CONTRACT_UPI_QR.md](API_CONTRACT_UPI_QR.md); the backend serializers and the
frontend Zod schemas both answer to them.

## Taking payments before a gateway exists (UPI QR)

Until Razorpay is configured, the salon takes payment with its own UPI QR:

1. **Owner:** sign in at `/admin`, open **Payment QR**, upload a screenshot of
   the salon's UPI QR, optionally add the UPI ID (this gives phone users a
   one-tap "Open UPI app" button with the amount filled in), and enter the
   password to save.
2. **Customer:** places an order and is shown the QR and the exact amount. They
   pay in any UPI app, then type the 12-digit UPI reference (UTR). Their place
   in today's draw is held.
3. **Owner:** **To confirm** lists each claim with its amount, reference and
   phone number. Find it in your UPI app, then tap **Confirm received**. That
   marks it paid and gives it the next draw number. The customer's screen
   updates by itself. If the money isn't there, tap **Not received** instead.
4. **Winners:** **Refunds** shows what to send back under the
   reward-attributable rule. Send it by UPI (or cash), then record it.

Confirm payments on the day they arrive: a claim confirmed after midnight is
marked paid, but that day's draw has closed. Once a gateway is configured
(Phase 5), the QR switches off by itself (`gateway_configured()` in
`apps/payments/services.py`).

## Deployment

### Vercel (production)

Two Vercel projects deploy from this repo, in `sin1` (Singapore), and redeploy
on every push to `main` through Vercel's GitHub integration:

| Project | Root | URL |
|---|---|---|
| `saloon-shop-web` | `frontend/` | <https://saloon-shop-web.vercel.app> |
| `saloon-shop-api` | `backend/` | <https://saloon-shop-api.vercel.app> |

- **Database:** Neon Postgres (`saloon-db`, Singapore) from the Vercel
  Marketplace. Functions use the pooled `DATABASE_URL`; migrations use the
  direct `DATABASE_URL_UNPOOLED`.
- **Backend build** (`backend/vercel_build.py`, wired through
  `[tool.vercel.scripts]` in `pyproject.toml`) runs `migrate` and
  `createcachetable` on **production builds only**. Only `main` deploys the
  backend (`git.deploymentEnabled` in `backend/vercel.json`), because a
  preview would share the production database. `SEED_ON_BUILD=1` seeds a fresh database once;
  remove it afterwards.
- **No Redis, no Celery on Vercel.** The cache is Django's database cache.
  The midnight rollover is a Vercel Cron (`0 19 * * *` UTC = 00:30 IST) calling
  `/api/v1/internal/cron/daily-rollover` with `Authorization: Bearer $CRON_SECRET`.
  On Hobby, cron runs once a day and may fire up to an hour late. That is safe
  because campaigns are also provisioned lazily and reservations expire
  lazily.
- **Media uploads do not persist** (function filesystems are read-only and
  ephemeral). Object storage must be wired before the admin panel can upload
  images.
- **Hobby is for non-commercial use.** Move to Pro before taking real bookings.
  Pro also allows per-minute cron, which Phase 5 needs for payment reconciliation.

### Container images

`cd-images.yml` builds both production images on every push to `main` and pushes
them to GHCR:

```
ghcr.io/ukiaf11/saloon-shop/backend:latest
ghcr.io/ukiaf11/saloon-shop/frontend:latest
```

Also tagged by commit SHA, so a deploy can pin an exact build. The backend image
is smoke-tested with `manage.py check --deploy` before it is considered good.
Any host that runs containers can pull these. Vercel does not use them. They are
for any host that runs containers.

### GitHub Pages (the fallback preview)

`pages.yml` publishes a **static export** to
<https://ukiaf11.github.io/saloon-shop/>. Now that Vercel is live it runs
**only when started by hand** (Actions → Deploy preview to GitHub Pages → Run workflow).

Be precise about what this is. GitHub Pages serves static files; it cannot run
Node or Django. So the Pages site is a preview of the marketing page, not the
product:

| | Container deploy | GitHub Pages |
|---|---|---|
| Django API | yes | **no** |
| Services / hours / FAQs | live | frozen at build time, empty if no API was reachable |
| Checkout, payment, coupons, admin | yes | **cannot work** |
| On-demand revalidation (`revalidateTag`) | yes | no — content updates only when the workflow reruns |
| `next/image` optimization | yes | no — original bytes are shipped |
| Security headers from `next.config.ts` | yes | no — Pages sends its own |

It is **noindex by default**, so a site that cannot take a booking never
outranks the real one.

Optional repository variables (Settings → Secrets and variables → Actions → Variables):

| Variable | Effect |
|---|---|
| `PUBLIC_API_BASE_URL` | Point the Pages build at a publicly reachable API so real content is baked in. Unset ⇒ empty sections. |
| `PUBLIC_MEDIA_HOSTNAME` | Object-storage hostname, allowlisted for `next/image`. |
| `PAGES_ALLOW_INDEXING` | Set to `1` only once Pages really is production and checkout works. |

## Things to know before changing code

These are load-bearing. The full list is in [memory.md](memory.md) §5.

1. **Money is integer paise.** No floats in the money path, anywhere. Use
   `common.money` on the backend and `src/lib/money.ts` for display only.
2. **The browser sends `service_ids` and contact fields only.** The backend
   computes every price, discount and total; payment amounts are read from
   `Order.total_paise`, never from a request body.
3. **Idempotency comes from database unique constraints**, not application-level
   existence checks. The payment-verify and webhook paths race by design.
4. **Winning positions never leave the server** — not in an API response, a
   serializer, a log line or an error message. `common.masking` redacts them.
5. **Capacity admission happens under `SELECT ... FOR UPDATE`** on the
   `DailyCampaign` row. Use `common.locks`, which refuses to run outside a
   transaction.
6. **Never commit secrets.** `.env` is gitignored, pre-commit runs gitleaks, and
   CI scans history.
7. **Service prices change only through `catalog.services.change_service_price()`.**
   A direct `.save()` that alters `price_paise` raises — price history is an audit
   requirement, not a convenience.
8. **Public cache invalidation is explicit.** Adding a public endpoint means adding
   its key to `common/cache.py` and a signal that drops it. TTL is only a backstop.
9. **Order status changes only through `Order.transition_to()`.** The transition
   table in `apps/orders/state.py` is the whole state machine; an edge that is not
   in it raises rather than being written.
10. **Winning positions and the campaign seed never leave the server.** They are
   encrypted at rest with `common/crypto.py`, and `tests/test_no_secret_leaks.py`
   fails the build if a serializer, view or new caller touches them.
11. **Capacity is only ever taken through `reserve_slot()`**, which holds a row
   lock on the campaign for the whole check-and-insert. Anything that counts
   slots without that lock will oversell.
12. **The cart holds no money.** `frontend/src/lib/cart.tsx` stores service ids and
   quantities only — every rupee on screen comes from the server quote.
