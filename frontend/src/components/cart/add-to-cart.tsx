"use client";

/**
 * The client island inside an otherwise server-rendered service card.
 *
 * It shows Add until the service is selected, then a quantity stepper. No
 * price arithmetic happens here -- the totals come from the server quote.
 */

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

  if (!hydrated || quantity === 0) {
    return (
      <button
        type="button"
        onClick={() => add(serviceId)}
        className="bg-gold-500 text-ink-950 hover:bg-gold-400 rounded-full px-4 py-1.5 text-sm font-medium transition-colors"
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
      className="border-gold-500/60 flex items-center gap-1 rounded-full border"
      role="group"
      aria-label={`${serviceName} quantity`}
    >
      <button
        type="button"
        onClick={() => setQuantity(serviceId, quantity - 1)}
        className="text-ivory-100 hover:text-gold-400 px-3 py-1.5 text-lg leading-none transition-colors"
        aria-label={quantity === 1 ? `Remove ${serviceName}` : `Decrease ${serviceName}`}
      >
        −
      </button>
      <span
        className="text-ivory-50 min-w-5 text-center text-sm tabular-nums"
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
        className="text-ivory-100 hover:text-gold-400 px-3 py-1.5 text-lg leading-none transition-colors disabled:opacity-40"
        aria-label={`Increase ${serviceName}`}
      >
        +
      </button>
    </div>
  );
}
