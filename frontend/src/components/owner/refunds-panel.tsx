"use client";

/**
 * Winners' refunds. There is no gateway to send them, so each one is a task:
 * the owner sends the money from their UPI app (or in cash), then records it
 * here so the customer's booking page shows it as sent.
 */

import { useEffect, useId, useState } from "react";

import { formatInr } from "@/lib/money";
import { errorMessage, listRefunds, markRefundSent, SessionEnded } from "@/lib/owner-api";
import { formatUtr, isValidUtr, normaliseUtr } from "@/lib/upi";
import type { OwnerRefund } from "@/types/owner";

import { inputClass, Notice, whenText } from "./ui";

export function RefundsPanel({
  token,
  pending,
  onChanged,
  onSessionEnded,
}: {
  token: string;
  pending: OwnerRefund[];
  onChanged: () => void;
  onSessionEnded: () => void;
}) {
  const [sent, setSent] = useState<OwnerRefund[] | null>(null);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listRefunds(token, "sent")
      .then((result) => {
        if (!cancelled) setSent(result);
      })
      .catch((err: unknown) => {
        if (!cancelled && err instanceof SessionEnded) onSessionEnded();
      });
    return () => {
      cancelled = true;
    };
  }, [token, reloads, onSessionEnded]);

  return (
    <div className="space-y-5">
      {pending.length === 0 ? (
        <Notice tone="info">
          No refunds to send. Winners&apos; refunds appear here.
        </Notice>
      ) : (
        pending.map((refund) => (
          <RefundCard
            key={refund.id}
            refund={refund}
            token={token}
            onSent={() => {
              onChanged();
              setReloads((n) => n + 1);
            }}
            onSessionEnded={onSessionEnded}
          />
        ))
      )}

      {sent && sent.length > 0 ? (
        <section aria-labelledby="sent-refunds" className="pt-4">
          <h3 id="sent-refunds" className="font-display text-ink text-xl">
            Sent
          </h3>
          <ul className="mt-3 space-y-2">
            {sent.map((refund) => (
              <li key={refund.id} className="clay-well px-4 py-3 text-sm">
                <span className="text-ink font-bold">
                  {formatInr(refund.amount_paise)}
                </span>{" "}
                to {refund.customer.name} · {refund.order.public_order_number} ·{" "}
                {refund.method === "CASH"
                  ? "cash"
                  : `UPI ${refund.reference ? formatUtr(refund.reference) : ""}`}
                {refund.sent_at ? ` · ${whenText(refund.sent_at)}` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function RefundCard({
  refund,
  token,
  onSent,
  onSessionEnded,
}: {
  refund: OwnerRefund;
  token: string;
  onSent: () => void;
  onSessionEnded: () => void;
}) {
  const refId = useId();
  const [method, setMethod] = useState<"UPI" | "CASH">("UPI");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (method === "UPI" && !isValidUtr(reference)) {
      setError("Enter the 12-digit UPI reference of the refund you sent.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await markRefundSent(token, refund.id, method, normaliseUtr(reference));
      onSent();
    } catch (err) {
      if (err instanceof SessionEnded) return onSessionEnded();
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="clay p-5 sm:p-6">
      <p className="text-ink-muted text-xs font-extrabold tracking-[0.12em] uppercase">
        Refund to send · draw #{refund.participant_number}
      </p>
      <p className="font-display text-ink mt-1 text-3xl tabular-nums">
        {formatInr(refund.amount_paise)}
      </p>
      <p className="text-ink mt-2 text-sm font-semibold">
        {refund.customer.name} ·{" "}
        <a
          href={`tel:${refund.customer.phone}`}
          className="text-primary underline underline-offset-4"
        >
          {refund.customer.phone}
        </a>
      </p>
      <p className="text-ink-soft mt-1 text-sm">
        {refund.order.public_order_number}
        {refund.payment_reference
          ? ` · they paid with UPI ref ${formatUtr(refund.payment_reference)}`
          : ""}
      </p>
      {refund.free_services.length > 0 ? (
        <p className="text-ink-soft mt-1 text-sm">
          Also free for them: {refund.free_services.join(", ")}
        </p>
      ) : null}

      <form onSubmit={submit} className="mt-4 space-y-3" noValidate>
        <fieldset>
          <legend className="text-ink mb-2 text-sm font-bold">
            How did you send it?
          </legend>
          <div className="flex gap-2">
            {(["UPI", "CASH"] as const).map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={method === option}
                onClick={() => setMethod(option)}
                className={`min-h-11 flex-1 px-4 text-sm font-bold ${
                  method === option ? "clay-btn" : "clay-btn-soft text-ink-soft"
                }`}
              >
                {option === "UPI" ? "UPI transfer" : "Cash at the salon"}
              </button>
            ))}
          </div>
        </fieldset>

        {method === "UPI" ? (
          <div>
            <label htmlFor={refId} className="text-ink mb-2 block text-sm font-bold">
              UPI reference of your refund
            </label>
            <input
              id={refId}
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              inputMode="numeric"
              autoComplete="off"
              maxLength={16}
              placeholder="12 digits"
              className={`${inputClass} tracking-wider tabular-nums`}
            />
          </div>
        ) : null}

        {error ? <Notice tone="error">{error}</Notice> : null}

        <button
          type="submit"
          disabled={busy}
          className="clay-btn w-full px-6 py-3 text-sm font-bold"
        >
          {busy ? "Saving…" : `Mark ${formatInr(refund.amount_paise)} as sent`}
        </button>
      </form>
    </article>
  );
}
