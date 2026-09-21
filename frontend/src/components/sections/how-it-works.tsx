/**
 * The four steps, each with its own clay illustration. The #offers anchor is
 * the navbar's "How it works" link.
 *
 * Steps 2-4 depend on how customers pay. While the salon takes payment by its
 * own UPI QR, a person confirms each payment and there is no coupon yet, so
 * the copy says exactly that rather than promising a card gateway.
 */

import { CardArt, ChecklistArt, StarArt, TicketArt } from "@/components/clay/clay-art";

import { Section } from "./section";

type PaymentMethod = "upi_qr" | "gateway" | "unavailable";

const GATEWAY_STEPS = [
  {
    art: ChecklistArt,
    tile: "bg-peach",
    title: "Pick your services",
    body: "Choose what you want done. Two or more different services unlock 10% off — applied by us, not typed in by you.",
  },
  {
    art: CardArt,
    tile: "bg-lavender",
    title: "Pay securely",
    body: "Pay by UPI or card through our payment partner. We never see or store your card details.",
  },
  {
    art: StarArt,
    tile: "bg-butter",
    title: "See your result instantly",
    body: "The moment your payment is confirmed, you find out whether you landed one of the day's lucky slots.",
  },
  {
    art: TicketArt,
    tile: "bg-mint",
    title: "Show your coupon",
    body: "You get a QR coupon on screen. Show it at the salon — a winning coupon also lists your free services.",
  },
] as const;

const UPI_QR_STEPS = [
  GATEWAY_STEPS[0],
  {
    art: CardArt,
    tile: "bg-lavender",
    title: "Pay by UPI",
    body: "Scan the salon's UPI QR — or tap to open your UPI app on your phone — then enter the 12-digit UPI reference so we can match your payment.",
  },
  {
    art: StarArt,
    tile: "bg-butter",
    title: "See your result",
    body: "As soon as the salon confirms your payment, you find out whether you landed one of the day's lucky slots.",
  },
  {
    art: TicketArt,
    tile: "bg-mint",
    title: "Show your order number",
    body: "Show your order number at the salon. If you won, your booking lists your free services and any refund due.",
  },
] as const;

export function HowItWorksSection({
  paymentMethod = "gateway",
}: {
  paymentMethod?: PaymentMethod;
}) {
  const steps = paymentMethod === "upi_qr" ? UPI_QR_STEPS : GATEWAY_STEPS;
  return (
    <Section
      id="offers"
      eyebrow="How it works"
      title="Four easy steps to a lucky day"
      align="center"
    >
      {/* On a phone each step is a compact row, art beside text, so the four
          steps take one screen instead of three. From sm up they become
          centred cards. */}
      <ol className="grid gap-5 sm:grid-cols-2 sm:gap-6 lg:grid-cols-4">
        {steps.map(({ art: Art, tile, title, body }, index) => (
          <li
            key={title}
            className="clay relative flex items-start gap-4 p-4 text-left sm:block sm:p-6 sm:pt-8 sm:text-center"
          >
            <span
              aria-hidden="true"
              className="clay-btn absolute -top-3 -left-2 flex h-9 w-9 items-center justify-center text-base font-extrabold sm:-top-4 sm:left-1/2 sm:h-10 sm:w-10 sm:-translate-x-1/2 sm:text-lg"
            >
              {index + 1}
            </span>
            <div
              className={`${tile} flex h-20 w-20 shrink-0 items-center justify-center rounded-[1.25rem] sm:mx-auto sm:h-28 sm:w-28 sm:rounded-[1.75rem]`}
            >
              <Art size={58} className="sm:hidden" />
              <Art size={82} className="hidden sm:block" />
            </div>
            <div className="min-w-0">
              <h3 className="font-display text-ink text-lg sm:mt-5 sm:text-xl">
                {title}
              </h3>
              <p className="text-ink-soft mt-1 text-sm leading-relaxed sm:mt-2">{body}</p>
            </div>
          </li>
        ))}
      </ol>
    </Section>
  );
}
