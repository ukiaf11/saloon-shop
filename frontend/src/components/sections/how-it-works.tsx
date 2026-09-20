/**
 * How the booking and the daily campaign fit together. Server component.
 *
 * The copy is static rather than CMS-driven: it describes mechanics the backend
 * enforces (distinct-service discount, pre-generated lucky slots, QR coupon),
 * and those sentences should change with the rules, not from the content admin.
 *
 * Note the careful wording on step 3. Fewer participants than capacity means
 * fewer winners than slots (memory.md section 7), so nothing here promises a
 * number of daily winners -- and the exact campaign wording is still awaiting
 * owner sign-off.
 */

import { Section } from "./section";

const STEPS = [
  {
    title: "Pick your services",
    body: "Choose what you want done. Two or more different services unlock 10% off — the discount is applied by us, not typed in by you.",
  },
  {
    title: "Pay securely",
    body: "Pay by UPI or card through our payment partner. We never see or store your card details.",
  },
  {
    title: "See your result straight away",
    body: "The moment the payment is confirmed you find out whether you landed one of the day's lucky slots.",
  },
  {
    title: "Show your coupon",
    body: "You get a QR coupon on screen. Show it at the salon — a winning coupon also carries the free services and the refund status.",
  },
];

export function HowItWorksSection() {
  return (
    /* Phase 3 mounts the discount reveal at the top of this section -- the
       #offers anchor is the navbar's "Offers" link and points here. */
    <Section id="offers" title="How it works">
      <ol className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, index) => (
          <li
            key={step.title}
            className="border-ink-700/60 bg-ink-900 rounded-card border p-5"
          >
            <p
              aria-hidden="true"
              className="text-gold-500 font-[family-name:var(--font-display-loaded)] text-2xl"
            >
              {index + 1}
            </p>
            <h3 className="text-ivory-50 mt-2 text-base font-medium">{step.title}</h3>
            <p className="text-ivory-300 mt-2 text-sm leading-relaxed">{step.body}</p>
          </li>
        ))}
      </ol>
    </Section>
  );
}
