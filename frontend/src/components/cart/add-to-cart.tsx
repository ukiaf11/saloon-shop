"use client";

/**
 * The client island inside an otherwise server-rendered service card.
 *
 * It shows Add until the service is selected, then a quantity stepper. No
 * price arithmetic happens here -- the totals come from the server quote.
 */

import { BOOKING_ENABLED } from "@/lib/api";
import { MAX_QUANTITY_PER_SERVICE, useCart } from "@/lib/cart";

export function AddToCart({
  serviceId,
  serviceName,
}: {
  serviceId: string;
  serviceName: string;
}) {
  const { quantityOf, add, setQuantity, hydrated } = useCart();
  const quantity = quantityOf(serviceId);

  if (!BOOKING_ENABLED) {
    // A static preview with no API behind it: an Add button here could only
    // fail, so send people to the salon's contact details instead.
    return (
      <a
        href="#contact"
        className="clay-btn-soft text-ink-soft inline-flex min-h-11 items-center px-4 text-sm font-bold"
      >
        Book in salon
      </a>
    );
  }

  if (!hydrated || quantity === 0) {
    return (
      <button
        type="button"
        onClick={() => add(serviceId)}
        className="clay-btn min-h-11 px-5 text-sm font-bold"
        // "Add" alone is ambiguous when a screen reader reads the buttons out
        // of context, so the service name goes in the accessible name.
        aria-label={`Add ${serviceName}`}
      >
        Add
      </button>
    );
  }

  return (
    <div
      className="clay-well flex items-center gap-1 rounded-full! p-1"
      role="group"
      aria-label={`${serviceName} quantity`}
    >
      <button
        type="button"
        onClick={() => setQuantity(serviceId, quantity - 1)}
        className="clay-btn-soft flex h-10 w-10 items-center justify-center text-xl leading-none font-bold"
        aria-label={quantity === 1 ? `Remove ${serviceName}` : `Decrease ${serviceName}`}
      >
        −
      </button>
      <span
        className="text-ink min-w-7 text-center text-base font-extrabold tabular-nums"
        aria-live="polite"
        aria-atomic="true"
      >
        <span className="sr-only">{serviceName} quantity: </span>
        {quantity}
      </span>
      <button
        type="button"
        onClick={() => add(serviceId)}
        disabled={quantity >= MAX_QUANTITY_PER_SERVICE}
        className="clay-btn flex h-10 w-10 items-center justify-center text-xl leading-none font-bold"
        aria-label={`Increase ${serviceName}`}
      >
        +
      </button>
    </div>
  );
}
