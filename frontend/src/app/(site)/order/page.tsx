import type { Metadata } from "next";
import { Suspense } from "react";

import { OrderStatusView } from "@/components/order/order-status";

export const metadata: Metadata = {
  title: "Your booking",
  // A booking page is personal: its URL carries the order's id.
  robots: { index: false, follow: false },
};

export default function OrderPage() {
  return (
    <section className="mx-auto max-w-lg px-4 py-12 sm:py-16">
      {/* The id comes from the query string, which is only known in the
          browser; Suspense lets the rest of the page prerender around it. */}
      <Suspense
        fallback={
          <p className="text-ink-soft py-10 text-center">Loading your booking…</p>
        }
      >
        <OrderStatusView />
      </Suspense>
    </section>
  );
}
