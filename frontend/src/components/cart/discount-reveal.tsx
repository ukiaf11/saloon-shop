"use client";

/**
 * The moment the multi-service discount unlocks.
 *
 * Doc 3 section 9: brief, and above all *explanatory* -- the customer should
 * understand exactly why the price dropped, not just see a badge flash. It
 * animates only on the transition into eligibility, never on every re-render,
 * and respects prefers-reduced-motion via the global rule in globals.css.
 */

import { AnimatePresence, motion } from "motion/react";

import { formatInr } from "@/lib/money";

export function DiscountReveal({
  eligible,
  discountPercent,
  configuredDiscountPercent,
  discountPaise,
  distinctCount,
  minDistinctServices,
}: {
  eligible: boolean;
  /** Applied rate -- 0 when not eligible. */
  discountPercent: number;
  /** Campaign rate, used to name the incentive before it unlocks. */
  configuredDiscountPercent: number;
  discountPaise: number;
  distinctCount: number;
  minDistinctServices: number;
}) {
  const remaining = Math.max(minDistinctServices - distinctCount, 0);

  return (
    <AnimatePresence mode="wait" initial={false}>
      {eligible ? (
        <motion.p
          key="unlocked"
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="bg-mint text-ink inline-flex flex-wrap items-baseline gap-x-2 rounded-full px-3.5 py-1 text-sm"
          // The discount appearing is a meaningful change, so announce it.
          role="status"
        >
          {/* Short enough for one line at 360px, while still saying WHY the
              price dropped -- Doc 3 section 9 asks for exactly that. */}
          <span className="font-extrabold">Multi-service {discountPercent}% off</span>
          <span className="font-semibold">· you save {formatInr(discountPaise)}</span>
        </motion.p>
      ) : remaining > 0 ? (
        <motion.p
          key="locked"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="text-ink-soft text-sm font-semibold"
        >
          Add {remaining} more {remaining === 1 ? "service" : "services"} to unlock{" "}
          {configuredDiscountPercent > 0
            ? `${configuredDiscountPercent}% off`
            : "the multi-service offer"}
          .
        </motion.p>
      ) : null}
    </AnimatePresence>
  );
}
