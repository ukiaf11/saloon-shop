"use client";

/**
 * Paying by the salon's UPI QR, and what happens after.
 *
 * Three states, all read from the order the API returns -- never from what
 * this component assumes happened:
 *
 *   pay      -> the QR, a one-tap UPI link on phones, and the reference form
 *   waiting  -> the claim is with the salon; this polls until they decide
 *   decided  -> paid, and the draw result (or why there was no draw entry)
 *
 * Used by the checkout drawer and by the /order page a customer comes back to.
 */

import { useEffect, useId, useState } from "react";

import { StarArt } from "@/components/clay/clay-art";
import { ApiError } from "@/lib/api";
import { formatInr } from "@/lib/money";
import { fetchOrder, qrImageUrl, submitUpiReference } from "@/lib/payments";
import { isValidUtr, normaliseUtr, upiPayLink } from "@/lib/upi";
import type { Order, OrderLucky, PaymentOptions } from "@/types/api";

const POLL_MS = 10_000;

type UpiOptions = NonNullable<PaymentOptions["upi_qr"]>;

/** Plain-language reasons a paid booking has no draw number. */
export function skipReasonText(reason: OrderLucky["reason"], paid: boolean): string {
  switch (reason) {
    case "REPEAT_ENTRY":
      return "This phone number already has an entry in today's lucky draw, so this booking is not entered again. The booking itself is fine.";
    case "DAY_FULL":
      return "Today's lucky draw was already full, so this booking is not entered. The booking itself is fine.";
    case "DAY_CLOSED":
      return paid
        ? "Your payment was confirmed after that day's lucky draw had closed, so it could not be entered."
        : "That day's lucky draw has closed, so this booking cannot be entered.";
    case "HOLD_EXPIRED":
      return "Your place in the lucky draw expired before the payment was confirmed.";
    case "NOT_RUNNING":
      return "There is no lucky draw running for this booking.";
    default:
      return "";
  }
}

export function UpiPaymentPanel({
  order,
  upi,
  headingId,
  onOrderChange,
}: {
  order: Order;
  upi: UpiOptions | null;
  headingId: string;
  onOrderChange: (order: Order) => void;
}) {
  const [editing, setEditing] = useState(false);
  const status = order.payment.status;

  // Poll only while the salon is deciding, and only while someone is looking.
  useEffect(() => {
    if (status !== "awaiting_confirmation") return;
    let stopped = false;
    const refresh = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const next = await fetchOrder(order.id);
        if (!stopped) onOrderChange(next);
      } catch {
        // A missed refresh just means the next one tries again; the state on
        // screen is still the last one the server confirmed.
      }
    };
    const timer = window.setInterval(refresh, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [order.id, status, onOrderChange]);

  if (status === "confirmed") {
    return <Decided order={order} headingId={headingId} />;
  }

  if (status === "awaiting_confirmation" && !editing) {
    return (
      <Waiting order={order} headingId={headingId} onCorrect={() => setEditing(true)} />
    );
  }

  // With no QR on offer (the owner switched it off after this order was
  // placed) PayStep still takes a reference: a customer who was mid-payment
  // must be able to record money they already sent. The server decides
  // whether it is still accepted.
  return (
    <PayStep
      order={order}
      upi={upi}
      headingId={headingId}
      correcting={editing}
      onCancelCorrect={() => setEditing(false)}
      onSubmitted={(next) => {
        setEditing(false);
        onOrderChange(next);
      }}
    />
  );
}

function OrderNumber({ order }: { order: Order }) {
  return (
    <span className="bg-lucky-soft text-ink rounded-lg px-2 py-0.5 font-extrabold whitespace-nowrap">
      {order.public_order_number}
    </span>
  );
}

// --- pay ---------------------------------------------------------------------

function PayStep({
  order,
  upi,
  headingId,
  correcting,
  onCancelCorrect,
  onSubmitted,
}: {
  order: Order;
  upi: UpiOptions | null;
  headingId: string;
  correcting: boolean;
  onCancelCorrect: () => void;
  onSubmitted: (order: Order) => void;
}) {
  const inputId = useId();
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [saveNote, setSaveNote] = useState<string | null>(null);

  const amount = formatInr(order.total_paise);
  const qrUrl = upi ? qrImageUrl(upi.qr_image_version) : "";
  const payLink = upi?.upi_id
    ? upiPayLink({
        upiId: upi.upi_id,
        payeeName: upi.payee_name,
        amountPaise: order.total_paise,
        note: order.public_order_number,
      })
    : null;
  const rejected = order.payment.status === "rejected";

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!isValidUtr(reference)) {
      setError("Enter the 12-digit UPI reference number from your payment app.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      onSubmitted(await submitUpiReference(order.id, normaliseUtr(reference)));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "We could not send your reference. Check your connection and try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const saveQr = async () => {
    setSaveNote(null);
    try {
      const response = await fetch(qrUrl, { credentials: "omit" });
      if (!response.ok) throw new Error(String(response.status));
      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "salon-upi-qr.png";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
      setSaveNote(
        "Saved. In your UPI app, choose “Scan QR”, then pick it from your gallery.",
      );
    } catch {
      window.open(qrUrl, "_blank", "noopener");
    }
  };

  return (
    <div>
      <p className="text-ink-muted text-xs font-extrabold tracking-[0.12em] uppercase">
        Booking {order.public_order_number}
      </p>
      <h2 id={headingId} className="font-display text-ink mt-1 text-3xl">
        {correcting
          ? "Correct your reference"
          : upi
            ? `Pay ${amount} by UPI`
            : "Pay at the salon"}
      </h2>

      {!upi && !correcting ? (
        <p className="text-ink-soft mt-3">
          UPI QR payment is not available right now — please pay{" "}
          <strong className="text-ink">{amount}</strong> at the salon and show your order
          number <OrderNumber order={order} />.{" "}
          <span className="text-ink font-semibold">
            Already paid by UPI? Enter the reference below so the salon can match it.
          </span>
        </p>
      ) : null}

      {rejected && !correcting ? (
        <p
          role="alert"
          className="bg-rose text-danger mt-4 rounded-2xl px-4 py-3 text-sm font-semibold"
        >
          The salon could not find your earlier payment
          {order.payment.rejection_reason ? ` (“${order.payment.rejection_reason}”)` : ""}
          . Check the reference number and send it again, or pay and enter the new one.
        </p>
      ) : null}

      {upi && !correcting ? (
        <>
          <ol className="text-ink-soft mt-4 space-y-2 text-sm leading-relaxed">
            <li>
              <span className="text-ink font-extrabold">1.</span> Pay exactly{" "}
              <strong className="text-ink">{amount}</strong> with any UPI app
              <span className="sm:hidden">
                {" "}
                — tap the button, or save the QR and scan it from your gallery
              </span>
              <span className="hidden sm:inline">
                {" "}
                by scanning this QR with your phone
              </span>
              .
            </li>
            <li>
              <span className="text-ink font-extrabold">2.</span> Enter the 12-digit UPI
              reference (UTR) from the payment success screen below.
            </li>
          </ol>

          <figure className="clay-well mx-auto mt-5 flex w-full max-w-[18rem] flex-col items-center p-4">
            {/* A plain <img>: the QR must reach the customer byte-for-byte, and
                the image optimizer would re-encode it lossily. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={qrUrl}
              alt={`UPI QR code to pay ${upi.payee_name ?? "the salon"}`}
              width={240}
              height={240}
              className="aspect-square w-full max-w-[15rem] rounded-2xl bg-white object-contain p-2"
            />
            <figcaption className="text-ink-soft mt-3 text-center text-sm">
              {upi.payee_name ? (
                <span className="text-ink block font-bold">{upi.payee_name}</span>
              ) : null}
              {upi.upi_id ? <span className="break-all">{upi.upi_id}</span> : null}
            </figcaption>
          </figure>

          <div className="mt-4 flex flex-col gap-3 sm:hidden">
            {payLink ? (
              <a href={payLink} className="clay-btn px-6 py-3.5 text-center font-bold">
                Open UPI app · {amount}
              </a>
            ) : null}
            <button
              type="button"
              onClick={() => void saveQr()}
              className="clay-btn-soft px-6 py-3 text-sm font-bold"
            >
              Save QR to scan from gallery
            </button>
            {saveNote ? (
              <p className="text-success text-center text-sm font-semibold" role="status">
                {saveNote}
              </p>
            ) : null}
          </div>
        </>
      ) : null}

      <form onSubmit={submit} noValidate className="mt-6">
        <label htmlFor={inputId} className="text-ink mb-2 block text-sm font-bold">
          UPI reference number (UTR)
          <span className="text-danger" aria-hidden="true">
            {" "}
            *
          </span>
        </label>
        <input
          id={inputId}
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          inputMode="numeric"
          autoComplete="off"
          maxLength={16}
          placeholder="e.g. 4123 5678 9012"
          aria-invalid={Boolean(error)}
          aria-describedby={`${inputId}-hint${error ? ` ${inputId}-error` : ""}`}
          className="clay-well text-ink placeholder:text-ink-muted w-full px-4 py-3 font-semibold tracking-wider tabular-nums placeholder:font-normal placeholder:tracking-normal"
        />
        <p id={`${inputId}-hint`} className="text-ink-muted mt-1.5 text-xs">
          12 digits. Your UPI app shows it as “UPI Ref No.”, “UTR” or “Transaction ID”.
        </p>
        {error ? (
          <p id={`${inputId}-error`} className="text-danger mt-1.5 text-sm" role="alert">
            {error}
          </p>
        ) : null}

        <div className="mt-5 flex gap-3">
          {correcting ? (
            <button
              type="button"
              onClick={onCancelCorrect}
              className="clay-btn-soft flex-1 px-6 py-3.5 text-sm font-bold"
            >
              Cancel
            </button>
          ) : null}
          <button
            type="submit"
            disabled={submitting}
            className="clay-btn flex-[2] px-6 py-3.5 text-sm font-bold"
          >
            {submitting
              ? "Sending…"
              : correcting
                ? "Send corrected reference"
                : `I've paid ${amount}`}
          </button>
        </div>
      </form>
    </div>
  );
}

// --- waiting -----------------------------------------------------------------

function Waiting({
  order,
  headingId,
  onCorrect,
}: {
  order: Order;
  headingId: string;
  onCorrect: () => void;
}) {
  const lucky = order.lucky;
  return (
    <div>
      <p className="text-ink-muted text-xs font-extrabold tracking-[0.12em] uppercase">
        Booking {order.public_order_number}
      </p>
      <h2 id={headingId} className="font-display text-ink mt-1 text-3xl">
        Payment sent for checking
      </h2>
      <div role="status" aria-live="polite">
        <p className="text-ink-soft mt-3 leading-relaxed">
          The salon is checking its UPI account for{" "}
          <strong className="text-ink">{formatInr(order.total_paise)}</strong>
          {order.payment.reference_last4 ? (
            <>
              {" "}
              with reference ending{" "}
              <strong className="text-ink tabular-nums">
                {order.payment.reference_last4}
              </strong>
            </>
          ) : null}
          . This page updates by itself.
        </p>
        <p className="bg-butter text-ink mt-4 flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold">
          <span
            aria-hidden="true"
            className="bg-primary inline-block h-2.5 w-2.5 shrink-0 animate-pulse rounded-full motion-reduce:animate-none"
          />
          {lucky.status === "held"
            ? "Your place in today's lucky draw is held while the salon confirms your payment."
            : lucky.status === "not_entered"
              ? skipReasonText(lucky.reason, false)
              : "Waiting for the salon to confirm your payment."}
        </p>
      </div>
      <button
        type="button"
        onClick={onCorrect}
        className="text-primary hover:text-primary-hover mt-5 text-sm font-bold underline underline-offset-4"
      >
        Entered the wrong reference? Correct it
      </button>
    </div>
  );
}

// --- decided -----------------------------------------------------------------

function Decided({ order, headingId }: { order: Order; headingId: string }) {
  const lucky = order.lucky;
  const won = lucky.status === "won";

  return (
    <div role="status" aria-live="polite">
      <p className="text-ink-muted text-xs font-extrabold tracking-[0.12em] uppercase">
        Booking {order.public_order_number}
      </p>
      {won ? (
        <div className="mt-2 flex items-center gap-4">
          <div className="bg-lucky-soft flex h-20 w-20 shrink-0 items-center justify-center rounded-[1.5rem]">
            <StarArt size={60} />
          </div>
          <h2 id={headingId} className="font-display text-ink text-3xl leading-tight">
            You won a lucky slot!
          </h2>
        </div>
      ) : (
        <h2 id={headingId} className="font-display text-ink mt-1 text-3xl">
          Payment confirmed
        </h2>
      )}

      {won ? (
        <div className="mt-4 space-y-3 text-sm leading-relaxed">
          <p className="text-ink-soft">
            Your draw number{" "}
            <strong className="text-ink">#{lucky.participant_number}</strong> is one of
            today&apos;s lucky slots.
          </p>
          {lucky.free_services.length > 0 ? (
            <p className="bg-mint text-ink rounded-2xl px-4 py-3 font-semibold">
              Free for you: {lucky.free_services.join(", ")}
            </p>
          ) : null}
          {lucky.refund_paise > 0 ? (
            <p className="bg-butter text-ink rounded-2xl px-4 py-3 font-semibold">
              {lucky.refund_status === "sent"
                ? `${formatInr(lucky.refund_paise)} has been refunded to you.`
                : `The salon will refund ${formatInr(lucky.refund_paise)} to you.`}
            </p>
          ) : null}
        </div>
      ) : lucky.status === "not_won" ? (
        <p className="text-ink-soft mt-3 leading-relaxed">
          Your draw number was{" "}
          <strong className="text-ink">#{lucky.participant_number}</strong> — not a lucky
          slot this time. Thank you for booking with us!
        </p>
      ) : lucky.status === "not_entered" ? (
        <p className="text-ink-soft mt-3 leading-relaxed">
          {skipReasonText(lucky.reason, true)}
        </p>
      ) : null}

      <p className="text-ink-soft mt-5 text-sm">
        Show your order number <OrderNumber order={order} /> at the salon.
      </p>
    </div>
  );
}
