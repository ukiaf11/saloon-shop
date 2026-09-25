"use client";

/**
 * Collects the minimum the salon needs, places the order, then takes payment.
 *
 * While no payment gateway is configured, payment is the salon's UPI QR (see
 * upi-payment.tsx). With neither a gateway nor a QR, the success state says
 * plainly that nothing has been charged — telling someone their booking is
 * paid when it is not would be a lie the salon has to resolve at the counter.
 *
 * Validation is duplicated on purpose: the Zod schema here is a courtesy that
 * catches typos without a round trip, and the server validates again because
 * it cannot trust anything this file produces.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "motion/react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useCart } from "@/lib/cart";
import { formatInr } from "@/lib/money";
import { createOrder, newIdempotencyKey } from "@/lib/orders";
import { fetchPaymentOptions, rememberOrder } from "@/lib/payments";
import { useFocusTrap } from "@/lib/use-focus-trap";
import type { Order, PaymentOptions, Quote } from "@/types/api";

import { UpiPaymentPanel } from "./upi-payment";

const checkoutSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "Please enter your name.")
    .max(120, "That name is too long."),
  phone: z
    .string()
    .trim()
    .min(10, "Enter a 10-digit mobile number.")
    // Permissive on formatting, strict on substance: the server normalises
    // spacing, dashes and the +91 prefix, so rejecting them here would only
    // frustrate someone who typed their number the way they always do.
    .regex(/^[+\d][\d\s-]{8,17}$/, "Enter a valid mobile number.")
    .refine((v) => v.replace(/\D/g, "").length >= 10, "Enter a valid mobile number."),
  email: z.union([z.literal(""), z.email("Enter a valid email address.")]).optional(),
});

type CheckoutValues = z.infer<typeof checkoutSchema>;

/**
 * Payment options, retried once. A failure here must never be read as "online
 * payment is not live": the order exists, and the customer may be one retry
 * away from the salon's QR.
 */
async function loadOptionsWithRetry(): Promise<PaymentOptions | null> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      return await fetchPaymentOptions();
    } catch {
      if (attempt === 0) await new Promise((r) => setTimeout(r, 800));
    }
  }
  return null;
}

export function CheckoutDrawer({
  onClose,
  quote,
}: {
  onClose: () => void;
  quote: Quote | null;
}) {
  const cart = useCart();
  const [submitting, setSubmitting] = useState(false);
  const [placed, setPlaced] = useState<Order | null>(null);
  // undefined while loading; null when the options could not be fetched.
  const [options, setOptions] = useState<PaymentOptions | null | undefined>(undefined);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef);

  // Generated once per mount, and the parent mounts this component once per
  // checkout attempt. Reusing it across retries is what stops a
  // failed-then-retried submit creating two orders.
  const [idempotencyKey] = useState(newIdempotencyKey);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CheckoutValues>({
    resolver: zodResolver(checkoutSchema),
    defaultValues: { name: "", phone: "", email: "" },
  });

  useEffect(() => {
    // Move focus into the dialog so keyboard and screen-reader users are not
    // left behind on the page underneath.
    const t = setTimeout(() => firstFieldRef.current?.focus(), 50);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const onSubmit = handleSubmit(async (values) => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const order = await createOrder(
        cart.lines,
        { name: values.name, phone: values.phone, email: values.email || undefined },
        idempotencyKey,
      );
      setPlaced(order);
      rememberOrder({ id: order.id, number: order.public_order_number });
      cart.clear();
      reset();
      setOptions(await loadOptionsWithRetry());
    } catch (err) {
      setSubmitError(
        err instanceof Error
          ? err.message
          : "We could not place your order. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  });

  const { ref: nameFormRef, ...nameField } = register("name");

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
    >
      <button
        type="button"
        aria-label="Close checkout"
        onClick={onClose}
        className="absolute inset-0 bg-[#3a2a22]/45 backdrop-blur-sm"
      />

      <motion.div
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 40, opacity: 0 }}
        transition={{ duration: 0.2 }}
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="checkout-title"
        className="clay relative m-3 max-h-[92dvh] w-full max-w-lg overflow-y-auto p-6 sm:p-8"
      >
        {placed && options === undefined ? (
          <p
            id="checkout-title"
            role="status"
            className="text-ink-soft py-10 text-center"
          >
            Preparing payment…
          </p>
        ) : placed && options === null ? (
          <div>
            <h2 id="checkout-title" className="font-display text-ink text-3xl">
              Booking saved
            </h2>
            <p className="text-ink-soft mt-3">
              Your order number is{" "}
              <span className="bg-lucky-soft text-ink rounded-lg px-2 py-0.5 font-extrabold">
                {placed.public_order_number}
              </span>
              . We couldn&apos;t load the payment options just now — your booking is safe,
              and you can pay from your booking page.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => {
                  setOptions(undefined);
                  void loadOptionsWithRetry().then(setOptions);
                }}
                className="clay-btn flex-1 px-6 py-3 text-sm font-bold"
              >
                Try again
              </button>
              <Link
                href={`/order?id=${encodeURIComponent(placed.id)}`}
                onClick={onClose}
                className="clay-btn-soft flex-1 px-6 py-3 text-center text-sm font-bold"
              >
                Open booking page
              </Link>
            </div>
          </div>
        ) : placed &&
          (options?.method === "upi_qr" || placed.payment.status !== "not_started") ? (
          <div>
            <UpiPaymentPanel
              order={placed}
              upi={options?.upi_qr ?? null}
              headingId="checkout-title"
              onOrderChange={setPlaced}
            />
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              {/* Link, not <a>: it carries the base path on the GitHub Pages
                  build. Closing first, because the drawer lives in the site
                  layout and would otherwise stay open over the next page. */}
              <Link
                href={`/order?id=${encodeURIComponent(placed.id)}`}
                onClick={onClose}
                className="clay-btn-soft flex-1 px-6 py-3 text-center text-sm font-bold"
              >
                Open booking page
              </Link>
              <button
                type="button"
                onClick={onClose}
                className="clay-btn-soft flex-1 px-6 py-3 text-sm font-bold"
              >
                Close
              </button>
            </div>
            <p className="text-ink-muted mt-3 text-center text-xs">
              You can close this — your booking stays on this device under “Your booking”
              at the bottom of the page.
            </p>
          </div>
        ) : placed ? (
          <div>
            <h2 id="checkout-title" className="font-display text-ink text-3xl">
              Order created
            </h2>
            <p className="text-ink-soft mt-3">
              Your order number is{" "}
              <span className="bg-lucky-soft text-ink rounded-lg px-2 py-0.5 font-extrabold">
                {placed.public_order_number}
              </span>
              .
            </p>
            {/* Said plainly: nothing has been charged yet. */}
            <p className="bg-butter text-ink mt-5 rounded-2xl px-4 py-3 text-sm font-semibold">
              Online payment is not live yet. Please show this order number at the salon —
              no money has been taken.
            </p>
            <dl className="clay-well mt-5 px-5 py-4 text-sm">
              <div className="flex justify-between py-1">
                <dt className="text-ink-soft font-bold">Total</dt>
                <dd className="font-display text-ink text-xl tabular-nums">
                  {formatInr(placed.total_paise)}
                </dd>
              </div>
            </dl>
            <button
              type="button"
              onClick={() => {
                setPlaced(null);
                onClose();
              }}
              className="clay-btn mt-6 w-full px-6 py-3.5 font-bold"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <h2 id="checkout-title" className="font-display text-ink text-3xl">
              Your details
            </h2>

            {quote ? (
              <dl className="clay-well mt-5 px-5 py-4 text-sm">
                {quote.lines.map((line) => (
                  <div key={line.service_id} className="flex justify-between py-1">
                    <dt className="text-ink-soft font-semibold">
                      {line.name}
                      {line.quantity > 1 ? ` × ${line.quantity}` : ""}
                    </dt>
                    <dd className="text-ink font-semibold tabular-nums">
                      {formatInr(line.line_total_paise)}
                    </dd>
                  </div>
                ))}
                {quote.discount_paise > 0 ? (
                  <div className="text-success flex justify-between py-1 font-bold">
                    <dt>{quote.discount_percent}% multi-service offer</dt>
                    <dd className="tabular-nums">−{formatInr(quote.discount_paise)}</dd>
                  </div>
                ) : null}
                <div className="mt-2 flex justify-between border-t border-[#3a2a22]/10 pt-3">
                  <dt className="text-ink font-extrabold">Payable</dt>
                  <dd className="font-display text-ink text-xl tabular-nums">
                    {formatInr(quote.payable_paise)}
                  </dd>
                </div>
              </dl>
            ) : null}

            <div className="mt-5 space-y-4">
              <Field
                id="checkout-name"
                label="Name"
                error={errors.name?.message}
                required
              >
                <input
                  {...nameField}
                  ref={(el) => {
                    nameFormRef(el);
                    firstFieldRef.current = el;
                  }}
                  id="checkout-name"
                  autoComplete="name"
                  className={inputClass}
                  aria-invalid={Boolean(errors.name)}
                  aria-describedby={errors.name ? "checkout-name-error" : undefined}
                />
              </Field>

              <Field
                id="checkout-phone"
                label="Mobile number"
                error={errors.phone?.message}
                required
              >
                <input
                  {...register("phone")}
                  id="checkout-phone"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="90000 00000"
                  className={inputClass}
                  aria-invalid={Boolean(errors.phone)}
                  aria-describedby={errors.phone ? "checkout-phone-error" : undefined}
                />
              </Field>

              <Field
                id="checkout-email"
                label="Email"
                hint="optional"
                error={errors.email?.message}
              >
                <input
                  {...register("email")}
                  id="checkout-email"
                  type="email"
                  autoComplete="email"
                  className={inputClass}
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={errors.email ? "checkout-email-error" : undefined}
                />
              </Field>
            </div>

            {submitError ? (
              <p className="text-danger mt-4 text-sm" role="alert">
                {submitError}
              </p>
            ) : null}

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={onClose}
                className="clay-btn-soft flex-1 px-6 py-3.5 text-sm font-bold"
              >
                Back
              </button>
              <button
                type="submit"
                disabled={submitting || !quote}
                className="clay-btn flex-[2] px-6 py-3.5 text-sm font-bold"
              >
                {submitting
                  ? "Placing order…"
                  : quote
                    ? `Place order · ${formatInr(quote.payable_paise)}`
                    : "Place order"}
              </button>
            </div>
          </form>
        )}
      </motion.div>
    </motion.div>
  );
}

const inputClass =
  "clay-well w-full px-4 py-3 text-ink font-semibold placeholder:text-ink-muted placeholder:font-normal";

function Field({
  id,
  label,
  hint,
  error,
  required,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-ink mb-2 block text-sm font-bold">
        {label}
        {hint ? <span className="text-ink-muted font-semibold"> ({hint})</span> : null}
        {required ? (
          <span className="text-danger" aria-hidden="true">
            {" "}
            *
          </span>
        ) : null}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-danger mt-1.5 text-sm" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
