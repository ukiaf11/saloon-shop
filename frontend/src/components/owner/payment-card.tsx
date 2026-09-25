"use client";

/**
 * One UPI payment claim, with everything the owner needs to find it in their
 * UPI app: amount, the customer's 12-digit reference, name and phone.
 *
 * Confirming is two taps on purpose. It marks money as received and enters
 * the booking in the draw, and neither can be undone.
 */

import { useState } from "react";

import { formatInr } from "@/lib/money";
import {
  confirmPayment,
  errorMessage,
  rejectPayment,
  SessionEnded,
} from "@/lib/owner-api";
import { formatUtr } from "@/lib/upi";
import type { OwnerPayment } from "@/types/owner";

import { inputClass, Notice, SKIP_LABEL, whenText } from "./ui";

type Step = "idle" | "confirming" | "rejecting";

export function PaymentCard({
  payment,
  token,
  onDecided,
  onSessionEnded,
}: {
  payment: OwnerPayment;
  token: string;
  onDecided?: (payment: OwnerPayment) => void;
  onSessionEnded: () => void;
}) {
  const [step, setStep] = useState<Step>("idle");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const amount = formatInr(payment.amount_paise);
  const awaiting = payment.status === "awaiting_confirmation";

  const act = async (action: () => Promise<OwnerPayment>) => {
    setBusy(true);
    setError(null);
    try {
      const decided = await action();
      setStep("idle");
      onDecided?.(decided);
    } catch (err) {
      if (err instanceof SessionEnded) return onSessionEnded();
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const copyReference = async () => {
    try {
      await navigator.clipboard.writeText(payment.reference);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be blocked; the number is on screen to read anyway.
    }
  };

  return (
    <article className="clay p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-display text-ink text-3xl tabular-nums">{amount}</p>
          <p className="text-ink-muted mt-1 text-xs font-bold">
            {payment.order.public_order_number} · {whenText(payment.submitted_at)}
          </p>
        </div>
        <StatusChip payment={payment} />
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div className="clay-well px-4 py-3">
          <dt className="text-ink-muted text-xs font-extrabold tracking-[0.12em] uppercase">
            UPI reference
          </dt>
          <dd className="mt-1 flex items-center justify-between gap-2">
            <span className="text-ink font-extrabold tracking-wider tabular-nums">
              {formatUtr(payment.reference)}
            </span>
            <button
              type="button"
              onClick={() => void copyReference()}
              className="text-primary min-h-11 px-2 text-xs font-bold underline underline-offset-4"
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </dd>
        </div>
        <div className="clay-well px-4 py-3">
          <dt className="text-ink-muted text-xs font-extrabold tracking-[0.12em] uppercase">
            Customer
          </dt>
          <dd className="text-ink mt-1 font-semibold">
            {payment.customer.name} ·{" "}
            <a
              href={`tel:${payment.customer.phone}`}
              className="text-primary underline underline-offset-4"
            >
              {payment.customer.phone}
            </a>
          </dd>
        </div>
      </dl>

      <p className="text-ink-soft mt-3 text-sm">
        {payment.order.items
          .map((item) =>
            item.quantity > 1 ? `${item.name} × ${item.quantity}` : item.name,
          )
          .join(", ")}
      </p>

      <DrawLine payment={payment} />

      {awaiting && payment.draw_day_over ? (
        <div className="mt-3">
          <Notice tone="warning">
            This claim is from an earlier day. Confirming it now marks it paid, but it can
            no longer join that day&apos;s lucky draw.
          </Notice>
        </div>
      ) : null}

      {payment.rejection_reason ? (
        <p className="text-ink-soft mt-3 text-sm">Reason: {payment.rejection_reason}</p>
      ) : null}

      {error ? (
        <div className="mt-3">
          <Notice tone="error">{error}</Notice>
        </div>
      ) : null}

      {awaiting && step === "idle" ? (
        <div className="mt-5 flex gap-3">
          <button
            type="button"
            onClick={() => setStep("rejecting")}
            className="clay-btn-soft flex-1 px-4 py-3 text-sm font-bold"
          >
            Not received
          </button>
          <button
            type="button"
            onClick={() => setStep("confirming")}
            className="clay-btn flex-[2] px-4 py-3 text-sm font-bold"
          >
            Confirm received
          </button>
        </div>
      ) : null}

      {awaiting && step === "confirming" ? (
        <div className="bg-butter mt-5 rounded-2xl p-4">
          <p className="text-ink text-sm font-semibold">
            Did <strong>{amount}</strong> with reference{" "}
            <strong className="tabular-nums">{formatUtr(payment.reference)}</strong>{" "}
            arrive in your account? Confirming marks the booking paid and gives it a draw
            number. It cannot be undone.
          </p>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={() => setStep("idle")}
              className="clay-btn-soft flex-1 px-4 py-3 text-sm font-bold"
            >
              Back
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void act(() => confirmPayment(token, payment.id, payment.reference))
              }
              className="clay-btn flex-[2] px-4 py-3 text-sm font-bold"
            >
              {busy ? "Confirming…" : "Yes, received"}
            </button>
          </div>
        </div>
      ) : null}

      {awaiting && step === "rejecting" ? (
        <div className="bg-rose mt-5 rounded-2xl p-4">
          <label
            htmlFor={`reason-${payment.id}`}
            className="text-ink mb-2 block text-sm font-bold"
          >
            Why?{" "}
            <span className="text-ink-muted font-semibold">(the customer sees this)</span>
          </label>
          <input
            id={`reason-${payment.id}`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={200}
            placeholder="e.g. No payment with this reference"
            className={inputClass}
          />
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={() => setStep("idle")}
              className="clay-btn-soft flex-1 px-4 py-3 text-sm font-bold"
            >
              Back
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void act(() =>
                  rejectPayment(token, payment.id, payment.reference, reason),
                )
              }
              className="clay-btn flex-[2] px-4 py-3 text-sm font-bold"
            >
              {busy ? "Rejecting…" : "Reject payment"}
            </button>
          </div>
        </div>
      ) : null}
    </article>
  );
}

function StatusChip({ payment }: { payment: OwnerPayment }) {
  const [label, style] =
    payment.status === "awaiting_confirmation"
      ? ["To check", "bg-butter text-ink"]
      : payment.status === "confirmed"
        ? ["Received", "bg-mint text-success"]
        : ["Rejected", "bg-rose text-danger"];
  return (
    <span className={`${style} rounded-full px-3 py-1 text-xs font-extrabold uppercase`}>
      {label}
    </span>
  );
}

function DrawLine({ payment }: { payment: OwnerPayment }) {
  const draw = payment.draw;
  let text: string | null = null;
  let tone = "text-ink-soft";

  if (draw.status === "held") text = "Draw place held until you decide";
  else if (draw.status === "not_entered")
    text = SKIP_LABEL[draw.reason ?? ""] ?? "Not in the draw";
  else if (draw.status === "not_won") text = `Draw #${draw.participant_number} — no win`;
  else if (draw.status === "won") {
    tone = "text-success";
    const refund =
      draw.refund_paise > 0
        ? ` · refund ${formatInr(draw.refund_paise)} (${draw.refund_status === "sent" ? "sent" : "to send — see Refunds"})`
        : "";
    text = `Draw #${draw.participant_number} — WINNER${refund}`;
  }

  return text ? <p className={`${tone} mt-2 text-sm font-bold`}>{text}</p> : null;
}
