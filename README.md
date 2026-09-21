# Salon Lucky Customer Platform

[![CI](https://github.com/ukiaf11/saloon-shop/actions/workflows/ci.yml/badge.svg)](https://github.com/ukiaf11/saloon-shop/actions/workflows/ci.yml)
[![Images](https://github.com/ukiaf11/saloon-shop/actions/workflows/cd-images.yml/badge.svg)](https://github.com/ukiaf11/saloon-shop/actions/workflows/cd-images.yml)
[![Pages](https://github.com/ukiaf11/saloon-shop/actions/workflows/pages.yml/badge.svg)](https://github.com/ukiaf11/saloon-shop/actions/workflows/pages.yml)

Mobile-first salon website with a daily lucky-slot campaign, online payment, QR
coupons and a role-based admin panel.

**Status:** Phases 1–4 complete (foundation; catalog & content; quote & orders; daily campaign & lucky engine). See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

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
| `GET /api/v1/readiness` | Readiness — checks Postgres and Redis |
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

Response shapes are fixed by [API_CONTRACT_PHASE2.md](API_CONTRACT_PHASE2.md) and
[API_CONTRACT_PHASE3.md](API_CONTRACT_PHASE3.md); the backend serializers and the
frontend Zod schemas both answer to them.

## Deployment

Two paths, and they are **not** equivalent.

### Container images (the real one)

`cd-images.yml` builds both production images on every push to `main` and pushes
them to GHCR:

```
ghcr.io/ukiaf11/saloon-shop/backend:latest
ghcr.io/ukiaf11/saloon-shop/frontend:latest
```

Also tagged by commit SHA, so a deploy can pin an exact build. The backend image
is smoke-tested with `manage.py check --deploy` before it is considered good.
Any host that runs containers can pull these. There is no deploy job yet because
there is no server yet — add one when there is.

### GitHub Pages (the fallback preview)

`pages.yml` publishes a **static export** to
<https://ukiaf11.github.io/saloon-shop/>.

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
