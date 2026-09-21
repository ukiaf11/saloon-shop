"use client";

/**
 * The running total. Sticky bottom bar on mobile, the same bar on desktop —
 * Doc 3 section 8 calls it out as a strong conversion feature, and it is the
 * one place the customer watches the discount arrive.
 *
 * Every number shown comes from the server quote. The only thing computed in
 * the browser is how many distinct services are selected, which decides what
 * *prompt* to show — never what anyone owes.
 */

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { CheckoutDrawer } from "@/components/checkout/checkout-drawer";
import { BOOKING_ENABLED } from "@/lib/api";
import { useCart } from "@/lib/cart";
import { formatInr } from "@/lib/money";
import { useQuote } from "@/lib/use-quote";

import { DiscountReveal } from "./discount-reveal";

export function SelectionCart() {
  const cart = useCart();
  const { quote, loading, error } = useQuote(cart.lines);
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  // BOOKING_ENABLED guards a stale cart too: a visitor can still hold items in
  // localStorage from when this origin had working Add buttons, and pricing
  // them on a preview with no API could only fail.
  const visible = BOOKING_ENABLED && cart.hydrated && cart.lines.length > 0;

  return (
    <>
      <AnimatePresence>
        {visible && (
          <motion.aside
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 260, damping: 30 }}
            className="fixed inset-x-0 bottom-0 z-30 px-3 pb-3 sm:px-4 sm:pb-4"
            aria-label="Your selection"
          >
            {/* A floating clay tray rather than a full-width strip: it reads as
                something resting over the page, in the same idiom as the navbar. */}
            <div className="clay mx-auto flex max-w-4xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3 sm:px-7 sm:py-4">
              <div className="min-w-0">
                <p className="text-ink text-sm font-extrabold">
                  {cart.distinctCount} {cart.distinctCount === 1 ? "service" : "services"}{" "}
                  selected
                  {cart.totalUnits > cart.distinctCount
                    ? ` · ${cart.totalUnits} items`
                    : null}
                </p>

                <div className="mt-1 min-h-6">
                  {error ? (
                    <p className="text-danger text-sm font-semibold" role="alert">
                      {error}
                    </p>
                  ) : quote ? (
                    <DiscountReveal
                      eligible={quote.eligible_for_discount}
                      discountPercent={quote.discount_percent}
                      configuredDiscountPercent={quote.configured_discount_percent}
                      discountPaise={quote.discount_paise}
                      distinctCount={quote.distinct_service_count}
                      minDistinctServices={quote.min_distinct_services}
                    />
                  ) : null}
                </div>
              </div>

              <div className="flex items-center justify-between gap-5 sm:justify-end">
                <div className="text-right">
                  {/* aria-live so the total is announced when it changes, which
                      is the whole point of the bar for a screen-reader user. */}
                  <p
                    className="font-display text-ink text-2xl tabular-nums"
                    aria-live="polite"
                    aria-atomic="true"
                  >
                    {quote ? (
                      formatInr(quote.payable_paise)
                    ) : (
                      <span className="text-ink-muted font-body text-base">
                        {loading ? "Pricing…" : "—"}
                      </span>
                    )}
                  </p>
                  {quote && quote.discount_paise > 0 ? (
                    <p className="text-ink-muted text-xs font-semibold">
                      <span className="line-through">
                        {formatInr(quote.subtotal_paise)}
                      </span>{" "}
                      before discount
                    </p>
                  ) : null}
                </div>

                <button
                  type="button"
                  onClick={() => setCheckoutOpen(true)}
                  disabled={!quote || loading}
                  className="clay-btn px-7 py-3.5 text-sm font-bold whitespace-nowrap"
                >
                  Continue
                </button>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Keeps the sticky bar from covering the last section's content. */}
      {visible ? <div aria-hidden="true" className="h-36 sm:h-28" /> : null}

      {/* Mounted only while open, so every checkout attempt starts with fresh
          form state and a fresh idempotency key instead of being reset by an
          effect. */}
      <AnimatePresence>
        {checkoutOpen && (
          <CheckoutDrawer onClose={() => setCheckoutOpen(false)} quote={quote} />
        )}
      </AnimatePresence>
    </>
  );
}
