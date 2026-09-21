# API Contract — UPI QR Fallback, Owner Sign-in, Draw Decision

Authoritative request/response shapes for paying by the salon's own UPI QR
while no payment gateway is configured, and for the owner panel that confirms
those payments. Backend serializers and the frontend Zod schemas
(`frontend/src/types/api.ts`, `frontend/src/types/owner.ts`) both answer to
this file.

**The trust rule:** a customer's UPI reference is a *claim*, never a payment.
Nothing is paid, and no draw number is given, until the salon owner finds the
money in their own account and confirms it. That confirmation is the lucky
decision transaction of Doc 2 section 16: the payment, the order, the draw
number, the campaign counters and any refund owed commit together or not at
all.

Money is integer paise. Times are ISO 8601 UTC. Errors use the usual envelope:
`{"error": {"code", "message", "request_id"}}`.

---

## When this is active

`GET /payments/options` → `method`:

| `method` | Meaning |
|---|---|
| `upi_qr` | No gateway configured and the owner has uploaded a QR. Customers pay by QR. |
| `gateway` | A gateway is configured (Phase 5). The QR is ignored even if one is on file. |
| `unavailable` | Neither. Orders can be placed but not paid online. |

`apps.payments.services.gateway_configured()` is the single switch Phase 5
flips. Until then it is always `False`.

---

## Public endpoints

### `GET /api/v1/payments/options`

Throttle `public_read`. Never cached by the checkout.

```json
{
  "method": "upi_qr",
  "upi_qr": {
    "qr_image_version": "3c8d569c40d0ad5c",
    "upi_id": "salon@okaxis",
    "payee_name": "Upendra Salon"
  }
}
```

`upi_qr` is `null` unless `method` is `upi_qr`. `upi_id` and `payee_name` are
`null` when the owner left them empty.

### `GET /api/v1/payments/qr-image?v={qr_image_version}`

The QR as PNG bytes (`image/png`), **re-encoded by the server**: never the
bytes that were uploaded. `ETag` is the SHA-256 of the image and
`If-None-Match` returns `304`. With the current `v` the response is
`Cache-Control: public, max-age=31536000, immutable`; otherwise `max-age=60`.
`404` when there is no QR.

### `POST /api/v1/orders/{id}/upi-payment`

"I have paid, here is my UPI reference." Throttle `upi_claim`. Guarded, like
`GET /orders/{id}`, by the unguessable order UUID.

```json
{ "reference": "4123 5678 9012" }
```

- `reference` must be 12 digits after spaces and dashes are removed.
- Allowed from `DRAFT` or `PAYMENT_FAILED` (a rejected claim may be retried).
  The order moves to `PAYMENT_PENDING`.
- The same reference again is a no-op. A **different** reference while the
  claim is still awaiting confirmation **corrects** it. No second claim is
  created.
- Holds a place in today's draw (a `SlotReservation` lasting
  `UPI_CLAIM_HOLD_SECONDS`, default 36 h, in practice ended by the nightly
  close) or records why not. See `lucky.reason` below.

Response `200`: the full order, as `GET /orders/{id}`.

| Status | `code` | When |
|---|---|---|
| 400 | `validation_failed` | Not 12 digits |
| 404 | `not_found` | Unknown order |
| 409 | `upi_unavailable` | `method` is not `upi_qr` |
| 409 | `duplicate_reference` | That reference backs another live payment |
| 409 | `order_not_payable` | Already paid, or not in a payable state |
| 403 | `customer_blocked` | Customer blocked by the owner |

### Order payload additions (`GET /orders/{id}`, `POST /orders`, the claim)

```json
{
  "paid_at": null,
  "payment": {
    "status": "not_started | awaiting_confirmation | confirmed | rejected",
    "method": "upi_qr",
    "reference_last4": "9012",
    "rejection_reason": null,
    "submitted_at": "…",
    "decided_at": null
  },
  "lucky": {
    "status": "pending | held | not_entered | won | not_won",
    "reason": null,
    "participant_number": null,
    "campaign_date": null,
    "refund_paise": 0,
    "refund_status": null,
    "free_services": []
  }
}
```

- Only the **last four** digits of the reference are ever returned to the
  customer.
- `held` says a place is kept. It says nothing about winning. Winning positions
  never reach any response.
- `reason` (when `not_entered`): `REPEAT_ENTRY` (this phone already entered that
  day, per `max_entries_per_phone_per_day`), `DAY_FULL`, `DAY_CLOSED` (confirmed
  after the day ended, even if the nightly close had not run yet),
  `HOLD_EXPIRED`, `NOT_RUNNING` (no campaign configured).
- `refund_paise` for a winner follows REQUIREMENTS.md 8.1
  (reward-attributable-only): the net paid, after discount, of purchased lines
  in the day's reward package (`DailyCampaign.reward_snapshot`).
  `free_services` names the package services not purchased.
- `refund_status`: `pending` or `sent`. `null` when no refund is owed.

---

## Owner sign-in

Bearer tokens, not cookies. The site and the API are different sites (each
`*.vercel.app` host is its own), where a session cookie would be third-party.
Only the SHA-256 of a token is stored. Sessions last `ADMIN_SESSION_TTL_HOURS`
(12).

| Endpoint | Body | Response |
|---|---|---|
| `POST /api/v1/auth/login` | `{email, password}` | `{token, expires_at, user}` |
| `POST /api/v1/auth/logout` | — | `{"signed_out": true}` |
| `GET /api/v1/auth/me` | — | `{user, expires_at}` |
| `POST /api/v1/auth/password` | `{current_password, new_password}` | `{"password_changed": true}`. Every other session is revoked |

`user` = `{email, full_name, role, mfa_enabled}`. Authenticated calls send
`Authorization: Bearer <token>`.

Brute-force protection is in the database, not the cache (the cache throttle
fails open):

- 5 consecutive failures lock the account for 15 minutes, even against the right
  password: `423 account_locked`.
- 20 failures from one IP in 15 minutes: `429 too_many_attempts`.
- An unknown email and a wrong password both return
  `401 invalid_credentials` with the same message.

A wrong password on a **re-authenticated action** (payment settings, password
change) is `403 reauth_failed`, deliberately not 401: the session is still
valid. Clients treat any 401 as "signed out".

---

## Owner endpoints (role `OWNER` only)

Any other role gets `403`. Without a valid session the response is `401`.

### `GET /api/v1/owner/payment-settings`

```json
{
  "method": "upi_qr",
  "gateway_configured": false,
  "qr": { "version": "3c8d…", "width": 492, "height": 492, "updated_at": "…" },
  "upi_id": "salon@okaxis",
  "payee_name": "Upendra Salon"
}
```

### `PUT /api/v1/owner/payment-settings` (multipart)

Fields: `password` (required every time: this decides where customers' money
goes), `qr_image` (file), `remove_qr` (`true`), `upi_id`, `payee_name`. Absent
fields are left unchanged; `upi_id=""` clears it.

- The image must be PNG, JPEG, WebP or AVIF, at most 5 MB, and between
  200×200 and 6000×6000 pixels. It is re-encoded to PNG, EXIF-rotated,
  flattened onto white (a transparent QR would otherwise turn black), and
  scaled down to at most 1200 px. Metadata does not survive.
- Sending both `qr_image` and `remove_qr` is `400`.
- Every change is written to the audit log with the before and after SHA-256,
  UPI ID and name. The image bytes are never logged.

### `GET /api/v1/owner/payments?status=awaiting|confirmed|rejected`

Newest first, at most 100. Each item:

```json
{
  "id": "uuid", "status": "awaiting_confirmation", "reference": "412356789012",
  "amount_paise": 40500, "submitted_at": "…", "decided_at": null, "rejection_reason": null,
  "order": { "id": "uuid", "public_order_number": "SL-…", "status": "PAYMENT_PENDING",
             "total_paise": 40500, "created_at": "…", "items": [{ "name": "Hair Cutting", "quantity": 1 }] },
  "customer": { "name": "Rahul", "phone": "+919000000001" },
  "draw": { "…": "same shape as the order's lucky block" },
  "draw_day_over": false,
  "refund": null
}
```

The owner gets the **full** reference and phone number, because checking the
money needs them. `draw_day_over` warns that confirming will pay the order but
can no longer enter the day it was claimed on.

### `POST /api/v1/owner/payments/{id}/confirm`

One transaction: the payment becomes `CONFIRMED`, the order becomes `PAID` and
`paid_at` is set, then the lucky decision runs. If the order entered the draw,
`paid_count` goes up and it gets the next `participant_number`, which is
compared with the hidden positions. On a win, `winner_count` goes up and, if
the refund is above zero, a `Refund` is created and the order moves to
`REFUND_PENDING`. Returns the updated item. `409 payment_already_decided` if it
was already decided. Locks are always taken order first, then payment.

### `POST /api/v1/owner/payments/{id}/reject`

`{ "reason": "optional, ≤200 chars, shown to the customer" }`. The payment
becomes `REJECTED`, the order becomes `PAYMENT_FAILED`, and the draw hold is
cancelled. The reference is freed for a retry.

### `GET /api/v1/owner/refunds?status=pending|sent`

Each item carries `amount_paise`, `customer {name, phone}`, `order`,
`payment_reference` (the customer's own UTR; most UPI apps can pay the sender
back from it), `participant_number`, `free_services`, `method`, `reference` and
`sent_at`.

### `POST /api/v1/owner/refunds/{id}/mark-sent`

`{ "method": "UPI" | "CASH", "reference": "12 digits, required for UPI" }`.
The refund becomes `SENT` and the order `REFUNDED`. `409 refund_already_sent` if
it is already sent.

---

## State transitions used

```
DRAFT ──claim──▶ PAYMENT_PENDING ──confirm──▶ PAID ──(entered)──▶ LUCKY_DECIDED ──(won, refund>0)──▶ REFUND_PENDING ──mark-sent──▶ REFUNDED
                        │                         └─(not entered: stays PAID)
                        └──reject──▶ PAYMENT_FAILED ──claim──▶ PAYMENT_PENDING
```

Coupons (Phase 6) continue from `LUCKY_DECIDED` / `REFUNDED` to
`COUPON_ACTIVE`.
