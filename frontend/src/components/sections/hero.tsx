import Image from "next/image";

import heroPhoto from "@/assets/photos/barber-comb-portrait.webp";

import { CardArt, StarArt, TagArt } from "@/components/clay/clay-art";

/**
 * Signed-off marketing copy, held here rather than read from SiteContent.
 *
 * "Har Din 5 Lucky Slots" is the wording the owner signed off on (memory.md
 * section 4), and the campaign design hangs off it. It should not change
 * through a content edit, or vanish because /salon was briefly unreachable.
 */
const HERO = {
  eyebrow: "Premium grooming · Daily rewards",
  heading: "Har Din 5 Lucky Slots",
} as const;

function Badge({
  art,
  title,
  detail,
  className,
}: {
  art: React.ReactNode;
  title: string;
  detail: string;
  className: string;
}) {
  return (
    <div className={`clay-sm absolute items-center gap-3 px-3.5 py-2.5 ${className}`}>
      {art}
      <div className="leading-tight">
        <p className="text-ink text-sm font-extrabold">{title}</p>
        <p className="text-ink-muted text-xs font-semibold">{detail}</p>
      </div>
    </div>
  );
}

export function Hero({
  paymentMethod = "gateway",
}: {
  paymentMethod?: "upi_qr" | "gateway" | "unavailable";
}) {
  return (
    <section className="px-4 pt-8 pb-10 sm:pt-14 sm:pb-12">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
        <div>
          <p className="clay-sm text-primary inline-block px-4 py-1.5 text-xs font-bold tracking-[0.14em] uppercase">
            {HERO.eyebrow}
          </p>
          <h1 className="font-display text-ink mt-6 text-[2.75rem] leading-[1.02] sm:text-6xl lg:text-7xl">
            {HERO.heading}
          </h1>
          <p className="text-ink-soft mt-6 max-w-xl text-lg sm:text-xl">
            Hair cutting, shaving and a face massage —{" "}
            <strong className="text-ink">free</strong> for each day&apos;s lucky slots.
            Pick two or more services and <strong className="text-ink">save 10%</strong>{" "}
            automatically.
          </p>

          <div className="mt-9 flex flex-wrap gap-3">
            <a href="#services" className="clay-btn px-8 py-4 text-base font-bold">
              Book your services
            </a>
            <a href="#offers" className="clay-btn-soft px-7 py-4 text-base font-bold">
              How it works
            </a>
          </div>

          <p className="text-ink-muted mt-6 text-sm">
            Daily promotional capacity and campaign rules apply.{" "}
            <a
              href="/promotion-rules"
              className="text-primary py-3 font-semibold underline"
            >
              View promotion rules
            </a>
          </p>
        </div>

        <div className="relative mx-auto w-full max-w-md lg:max-w-none">
          {/* The photo sits in a clay frame: a raised surface with the image
              inset, so it belongs to the same world as the rest of the page. */}
          <div className="clay p-3 sm:p-4">
            <div className="relative aspect-4/5 overflow-hidden rounded-[1.5rem]">
              <Image
                src={heroPhoto}
                placeholder="blur"
                alt="A barber shaping a client's haircut with a comb and clippers"
                fill
                // Next 16 deprecates `priority`. Its docs recommend fetchPriority
                // over `preload` in most cases -- and on mobile this image stacks
                // below the heading, so it is not always the LCP element.
                loading="eager"
                fetchPriority="high"
                sizes="(min-width: 1024px) 520px, (min-width: 640px) 440px, 90vw"
                className="object-cover"
              />
              {/* CC BY 2.0 requires attribution; it goes with the image.
                  Bottom-right is the one corner no floating badge reaches at
                  any width -- verified at 360px, where the photo is narrow. */}
              <p className="absolute right-3 bottom-3 rounded-full bg-black/55 px-2.5 py-1 text-xs font-semibold text-white">
                Photo: Nenad Stojkovic · CC BY 2.0
              </p>
            </div>
          </div>

          <Badge
            art={<StarArt size={42} />}
            title="5 lucky slots"
            detail="drawn every day"
            className="clay-float -top-4 -left-3 flex sm:-left-8"
          />
          <Badge
            art={<TagArt size={40} />}
            title="10% off"
            detail="on 2+ services"
            className="clay-float-delayed top-1/2 -right-3 flex sm:-right-8"
          />
          <Badge
            art={<CardArt size={42} />}
            // Cards need the gateway; the QR fallback takes UPI only.
            title={paymentMethod === "upi_qr" ? "Pay by UPI" : "UPI & cards"}
            detail={paymentMethod === "upi_qr" ? "any UPI app" : "secure checkout"}
            // Hidden on a phone: at ~330px the photo cannot carry three
            // badges without one covering the photo credit.
            className="clay-float -bottom-5 left-8 hidden sm:flex"
          />
        </div>
      </div>
    </section>
  );
}
