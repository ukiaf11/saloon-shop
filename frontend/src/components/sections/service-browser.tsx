"use client";

/**
 * The service menu with a category filter.
 *
 * Client-side only for the filter state; every price still comes straight from
 * the API payload and goes through formatInr. Nothing here does arithmetic.
 *
 * Mobile first: on a phone each service is a compact horizontal row -- art on
 * the left, details on the right -- because eight tall cards would be several
 * screens of scrolling. From `sm` up they become vertical cards in a grid.
 */

import { useState } from "react";

import { AddToCart } from "@/components/cart/add-to-cart";
import { ServiceArt, tileFor } from "@/components/clay/clay-art";
import { Reveal } from "@/components/reveal";
import { formatInr } from "@/lib/money";
import type { Service, ServiceCategory } from "@/types/api";

import { SiteImage } from "./site-image";

/** Card width at the lg breakpoint is ~260px inside the 72rem container. */
const CARD_SIZES = "(min-width: 1024px) 270px, (min-width: 640px) 45vw, 96px";

const ALL = "all";
const OTHER = "other";

/** 90 -> "1 hr 30 min". Presentation only; the backend owns the number. */
export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} hr` : `${hours} hr ${rest} min`;
}

function ServiceCard({ service, index }: { service: Service; index: number }) {
  return (
    // Stagger within the row, not down the whole list, so the last card of a
    // long menu is not still waiting when the customer reaches it.
    <Reveal
      as="li"
      delay={(index % 4) * 90}
      className="clay clay-lift flex gap-4 p-3 sm:flex-col sm:gap-0"
    >
      <div
        className={`${tileFor(index)} relative flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-[1.25rem] sm:aspect-16/11 sm:h-auto sm:w-full sm:rounded-[1.5rem]`}
      >
        {service.image_url ? (
          <SiteImage
            src={service.image_url}
            // Empty alt on purpose: the service name is right beside the image,
            // so describing it again would only make a screen reader say it
            // twice (WCAG H67). The API has no alt_text for services.
            alt=""
            width={800}
            height={550}
            sizes={CARD_SIZES}
            className="lift-media h-full w-full object-cover"
          />
        ) : (
          <>
            <span className="lift-media sm:hidden">
              <ServiceArt slug={service.slug} size={72} />
            </span>
            <span className="lift-media hidden sm:block">
              <ServiceArt slug={service.slug} size={112} />
            </span>
          </>
        )}
        {service.is_featured ? (
          <span className="clay-sm text-primary absolute top-2 left-2 hidden px-2 py-0.5 text-xs font-extrabold tracking-wide uppercase sm:top-3 sm:left-3 sm:block sm:px-3 sm:py-1 sm:text-xs">
            Popular
          </span>
        ) : null}
      </div>

      <div className="flex min-w-0 flex-1 flex-col sm:px-2 sm:pt-4 sm:pb-2">
        {service.category || service.is_featured ? (
          <p className="text-primary flex flex-wrap items-center gap-2 text-xs font-extrabold tracking-[0.12em] uppercase">
            {service.category ? <span>{service.category.name}</span> : null}
            {service.is_featured ? (
              // On a phone the tile is too small to carry a badge without
              // covering the illustration, so it moves beside the label.
              <span className="bg-lucky-soft text-ink rounded-full px-2 py-0.5 tracking-wide sm:hidden">
                Popular
              </span>
            ) : null}
          </p>
        ) : null}
        <h3 className="font-display text-ink text-lg leading-snug sm:text-xl">
          {service.name}
        </h3>
        {service.description ? (
          // Two lines on a phone keeps each row compact; the full text shows
          // from sm up where there is room for it.
          <p className="text-ink-soft mt-1 line-clamp-2 text-sm leading-relaxed sm:line-clamp-none sm:flex-1">
            {service.description}
          </p>
        ) : (
          <div className="sm:flex-1" />
        )}

        <div className="mt-auto flex flex-wrap items-end justify-between gap-2 pt-3 sm:pt-4">
          <dl className="min-w-0">
            <dt className="sr-only">Price</dt>
            <dd className="font-display text-ink text-xl sm:text-2xl">
              {formatInr(service.price_paise)}
            </dd>
            <dt className="sr-only">Duration</dt>
            <dd className="text-ink-muted text-xs font-bold">
              {formatDuration(service.duration_minutes)}
            </dd>
          </dl>
          <AddToCart serviceId={service.id} serviceName={service.name} />
        </div>
      </div>
    </Reveal>
  );
}

export function ServiceBrowser({
  categories,
  services,
}: {
  categories: ServiceCategory[];
  services: Service[];
}) {
  const [active, setActive] = useState<string>(ALL);

  // Order comes from the API (display_order, then name). Re-sorting here would
  // make the page a second source of truth for it.
  const known = new Set(categories.map((c) => c.id));
  const filters = categories
    .filter((c) => services.some((s) => s.category?.id === c.id))
    .map((c) => ({ id: c.id, label: c.name }));

  // A service with no category, or one pointing at a category the list did not
  // include, still gets its own filter. A service must never silently vanish.
  const hasOther = services.some((s) => !s.category || !known.has(s.category.id));
  if (hasOther) filters.push({ id: OTHER, label: "More services" });

  const visible = services.filter((s) => {
    if (active === ALL) return true;
    if (active === OTHER) return !s.category || !known.has(s.category.id);
    return s.category?.id === active;
  });

  const chips = [{ id: ALL, label: "All" }, ...filters];

  return (
    <>
      {filters.length > 1 ? (
        // Scrolls sideways on a narrow screen instead of wrapping into a tall
        // block of chips. Negative margins let it run to the screen edge.
        <div
          role="group"
          aria-label="Filter services by category"
          className="-mx-4 mb-6 flex [scrollbar-width:none] gap-3 overflow-x-auto px-4 pt-1 pb-3 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 [&::-webkit-scrollbar]:hidden"
        >
          {chips.map((chip) => {
            const pressed = active === chip.id;
            return (
              <button
                key={chip.id}
                type="button"
                aria-pressed={pressed}
                onClick={() => setActive(chip.id)}
                className={`min-h-11 shrink-0 px-5 text-sm font-bold whitespace-nowrap ${
                  pressed ? "clay-btn" : "clay-btn-soft text-ink-soft"
                }`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
      ) : null}

      {/* A short count is announced on filter changes rather than making the
          whole list live, which would read out every card. */}
      <p className="sr-only" aria-live="polite">
        Showing {visible.length} {visible.length === 1 ? "service" : "services"}
      </p>

      <ul className="grid gap-4 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3 xl:grid-cols-4">
        {visible.map((service) => (
          // Colour keyed on the position in the full menu, so a card keeps its
          // tile colour when the filter changes instead of the tiles reshuffling.
          <ServiceCard
            key={service.id}
            service={service}
            index={services.indexOf(service)}
          />
        ))}
      </ul>
    </>
  );
}
