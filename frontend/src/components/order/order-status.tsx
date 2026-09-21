"use client";

/**
 * /order -- where a customer comes back to pay, or to see whether the salon
 * has confirmed their payment and how the draw went.
 *
 * The order comes from `?id=`, or failing that from the last order placed in
 * this browser. The page holds no state of its own: everything shown is what
 * the API says about the order right now.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import { UpiPaymentPanel } from "@/components/checkout/upi-payment";
import { ApiError } from "@/lib/api";
import { formatInr } from "@/lib/money";
import { fetchOrder, fetchPaymentOptions, recallOrder } from "@/lib/payments";
import type { Order, PaymentOptions } from "@/types/api";

type Load =
  | { state: "error"; message: string }
  | { state: "ready"; order: Order; options: PaymentOptions | null };

// The last order placed in this browser, read as an external store so the
// server render (which has no localStorage) and the browser agree.
const noSubscription = () => () => {};
const rememberedId = () => recallOrder()?.id ?? null;
const noRememberedId = () => null;

export function OrderStatusView() {
  const params = useSearchParams();
  const remembered = useSyncExternalStore(noSubscription, rememberedId, noRememberedId);
  const id = params.get("id") || remembered;
  // Keyed by order id: a result for another order is never shown for this one.
  const [result, setResult] = useState<{ id: string; load: Load } | null>(null);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    Promise.all([
      fetchOrder(id, controller.signal),
      fetchPaymentOptions(controller.signal).catch(() => null),
    ])
      .then(([order, options]) =>
        setResult({ id, load: { state: "ready", order, options } }),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setResult({
          id,
          load: {
            state: "error",
            message:
              error instanceof ApiError && error.status === 404
                ? "We could not find that booking."
                : "We could not load your booking. Check your connection and try again.",
          },
        });
      });
    return () => controller.abort();
  }, [id]);

  const load = id && result?.id === id ? result.load : null;

  if (id && !load) {
    return <p className="text-ink-soft py-10 text-center">Loading your booking…</p>;
  }

  if (!load || load.state === "error") {
    return (
      <div className="clay p-6 text-center sm:p-8">
        <h1 className="font-display text-ink text-3xl">Your booking</h1>
        <p className="text-ink-soft mt-3">
          {load?.state === "error"
            ? load.message
            : "There is no booking saved on this device. If you booked on another phone, open the booking page from there."}
        </p>
        <Link
          href="/#services"
          className="clay-btn mt-6 inline-block px-6 py-3 font-bold"
        >
          Browse services
        </Link>
      </div>
    );
  }

  const { order, options } = load;
  const upi = options?.method === "upi_qr" ? options.upi_qr : null;

  return (
    <div className="space-y-5">
      <h1 className="sr-only">Your booking</h1>
      <div className="clay p-6 sm:p-8">
        <UpiPaymentPanel
          order={order}
          upi={upi}
          headingId="order-title"
          onOrderChange={(next) =>
            setResult({ id: next.id, load: { state: "ready", order: next, options } })
          }
        />
      </div>

      <dl className="clay-well px-5 py-4 text-sm">
        {order.items.map((item) => (
          <div key={item.service_name} className="flex justify-between py-1">
            <dt className="text-ink-soft font-semibold">
              {item.service_name}
              {item.quantity > 1 ? ` × ${item.quantity}` : ""}
            </dt>
            <dd className="text-ink font-semibold tabular-nums">
              {formatInr(item.line_total_paise)}
            </dd>
          </div>
        ))}
        {order.discount_paise > 0 ? (
          <div className="text-success flex justify-between py-1 font-bold">
            <dt>{order.discount_percent_applied}% multi-service offer</dt>
            <dd className="tabular-nums">−{formatInr(order.discount_paise)}</dd>
          </div>
        ) : null}
        <div className="mt-2 flex justify-between border-t border-[#3a2a22]/10 pt-3">
          <dt className="text-ink font-extrabold">Total</dt>
          <dd className="font-display text-ink text-xl tabular-nums">
            {formatInr(order.total_paise)}
          </dd>
        </div>
      </dl>
    </div>
  );
}
