"use client";

/**
 * Collects the minimum the salon needs and places the order.
 *
 * Phase 3 ends at a created order. Payment is Phase 5, so the success state
 * says so plainly rather than implying money has moved — telling someone their
 * booking is confirmed when nothing has been charged would be a lie the salon
 * has to resolve at the counter.
 *
 * Validation is duplicated on purpose: the Zod schema here is a courtesy that
 * catches typos without a round trip, and the server validates again because
 * it cannot trust anything this file produces.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useCart } from "@/lib/cart";
import { formatInr } from "@/lib/money";
import { createOrder, newIdempotencyKey } from "@/lib/orders";
import type { Order, Quote } from "@/types/api";

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
  const [submitError, setSubmitError] = useState<string | null>(null);
  const firstFieldRef = useRef<HTMLInputElement>(null);

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
      cart.clear();
      reset();
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
        className="absolute inset-0 bg-black/70"
      />

      <motion.div
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 40, opacity: 0 }}
        transition={{ duration: 0.2 }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="checkout-title"
        className="border-ink-700 bg-ink-900 rounded-card relative max-h-[92dvh] w-full max-w-lg overflow-y-auto border p-6 sm:p-8"
      >
        {placed ? (
          <div>
            <h2
              id="checkout-title"
              className="text-ivory-50 font-[family-name:var(--font-display-loaded)] text-2xl"
            >
              Order created
            </h2>
            <p className="text-ivory-300 mt-3 text-sm">
              Your order number is{" "}
              <span className="text-gold-400 font-medium">
                {placed.public_order_number}
              </span>
              .
            </p>
            {/* Said plainly: nothing has been charged yet. */}
            <p className="text-warning mt-4 text-sm">
              Online payment is not live yet. Please show this order number at the salon —
              no money has been taken.
            </p>
            <dl className="border-ink-700 mt-5 border-t pt-4 text-sm">
              <div className="flex justify-between py-1">
                <dt className="text-ivory-500">Total</dt>
                <dd className="text-ivory-50 tabular-nums">
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
              className="bg-gold-500 text-ink-950 hover:bg-gold-400 mt-6 w-full rounded-full px-6 py-3 text-sm font-medium transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <h2
              id="checkout-title"
              className="text-ivory-50 font-[family-name:var(--font-display-loaded)] text-2xl"
            >
              Your details
            </h2>

            {quote ? (
              <dl className="border-ink-700 mt-5 border-y py-3 text-sm">
                {quote.lines.map((line) => (
                  <div key={line.service_id} className="flex justify-between py-1">
                    <dt className="text-ivory-300">
                      {line.name}
                      {line.quantity > 1 ? ` × ${line.quantity}` : ""}
                    </dt>
                    <dd className="text-ivory-100 tabular-nums">
                      {formatInr(line.line_total_paise)}
                    </dd>
                  </div>
                ))}
                {quote.discount_paise > 0 ? (
                  <div className="text-success flex justify-between py-1">
                    <dt>{quote.discount_percent}% multi-service offer</dt>
                    <dd className="tabular-nums">−{formatInr(quote.discount_paise)}</dd>
                  </div>
                ) : null}
                <div className="border-ink-700 mt-2 flex justify-between border-t pt-2">
                  <dt className="text-ivory-50 font-medium">Payable</dt>
                  <dd className="text-ivory-50 font-medium tabular-nums">
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
                className="border-ink-600 text-ivory-100 hover:border-gold-500 flex-1 rounded-full border px-6 py-3 text-sm transition-colors"
              >
                Back
              </button>
              <button
                type="submit"
                disabled={submitting || !quote}
                className="bg-gold-500 text-ink-950 hover:bg-gold-400 flex-[2] rounded-full px-6 py-3 text-sm font-medium transition-colors disabled:opacity-50"
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
  "w-full rounded-lg border border-ink-600 bg-ink-950 px-4 py-2.5 text-ivory-50 placeholder:text-ivory-500 focus-visible:border-gold-500";

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
      <label htmlFor={id} className="text-ivory-300 mb-1.5 block text-sm">
        {label}
        {hint ? <span className="text-ivory-500"> ({hint})</span> : null}
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
