/**
 * Services grid, grouped by category when the API returns any.
 *
 * Server component: nothing here is interactive yet. Selection -- the cart, the
 * quote call and the discount reveal -- is Phase 3 and will arrive as its own
 * client island around the Add control; the card itself stays on the server.
 */

import { formatInr } from "@/lib/money";
import type { Service, ServiceList } from "@/types/api";

import { Section } from "./section";
import { SiteImage } from "./site-image";

/** Card width at the lg breakpoint is ~352px inside the 72rem container. */
const CARD_SIZES = "(min-width: 1024px) 352px, (min-width: 640px) 45vw, 92vw";

/** 90 -> "1 hr 30 min". Presentation only; the backend owns the number. */
function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} hr` : `${hours} hr ${rest} min`;
}

function ServiceCard({
  service,
  titleTag: Title,
}: {
  service: Service;
  /** h3 in a flat list, h4 under a category heading -- heading order is a11y, not style. */
  titleTag: "h3" | "h4";
}) {
  return (
    <li className="border-ink-700/60 bg-ink-900 rounded-card flex flex-col overflow-hidden border">
      {service.image_url ? (
        <div className="bg-ink-800 aspect-4/3 w-full overflow-hidden">
          <SiteImage
            src={service.image_url}
            // Empty alt on purpose: the service name is right below the image,
            // so describing it again would only make a screen reader say it
            // twice (WCAG H67). The API has no alt_text for services.
            alt=""
            width={800}
            height={600}
            sizes={CARD_SIZES}
            className="h-full w-full object-cover"
          />
        </div>
      ) : null}

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start justify-between gap-3">
          <Title className="text-ivory-50 text-base font-medium">{service.name}</Title>
          {service.is_featured ? (
            <span className="border-gold-600/50 text-gold-400 shrink-0 rounded-full border px-2 py-0.5 text-[11px] tracking-wide uppercase">
              Featured
            </span>
          ) : null}
        </div>

        {service.description ? (
          <p className="text-ivory-300 mt-2 text-sm">{service.description}</p>
        ) : null}

        <dl className="mt-4 flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <div>
            <dt className="sr-only">Price</dt>
            {/* formatInr is the only way a price reaches the screen. */}
            <dd className="text-ivory-50 text-lg">{formatInr(service.price_paise)}</dd>
          </div>
          <div>
            <dt className="sr-only">Duration</dt>
            <dd className="text-ivory-500 text-sm">
              {formatDuration(service.duration_minutes)}
            </dd>
          </div>
        </dl>

        {/* Phase 3 owns selection. This is the finished affordance with nothing
            behind it yet -- disabled rather than silently inert, so nobody taps
            a dead control and wonders what happened. */}
        <button
          type="button"
          disabled
          // "Add" alone is ambiguous once a screen reader is reading the
          // buttons out of context; the visible word stays inside the name, so
          // voice control still reaches it.
          aria-label={`Add ${service.name}`}
          className="border-gold-600/60 text-gold-300 mt-5 w-full cursor-not-allowed rounded-full border px-4 py-2.5 text-sm font-medium opacity-80"
        >
          Add
        </button>
      </div>
    </li>
  );
}

function ServiceGrid({
  services,
  titleTag,
}: {
  services: Service[];
  titleTag: "h3" | "h4";
}) {
  return (
    <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {services.map((service) => (
        <ServiceCard key={service.id} service={service} titleTag={titleTag} />
      ))}
    </ul>
  );
}

export function ServicesSection({ services }: { services: ServiceList }) {
  const { categories, results } = services;

  // The section keeps its anchor even when empty: #services is a navbar link
  // and a dead anchor is worse than a quiet line of text.
  if (results.length === 0) {
    return (
      <Section id="services" title="Services">
        <p className="text-ivory-500 text-sm">
          Our service list is being updated. Call the salon and we will walk you through
          it.
        </p>
      </Section>
    );
  }

  // Order comes from the API (display_order, then name). Re-sorting here would
  // make the page a second source of truth for it.
  const knownCategoryIds = new Set(categories.map((category) => category.id));
  const groups = categories
    .map((category) => ({
      id: category.id,
      name: category.name,
      items: results.filter((service) => service.category?.id === category.id),
    }))
    .filter((group) => group.items.length > 0);

  // Anything uncategorised -- or pointing at a category the list did not
  // include -- still gets rendered. A service must never silently disappear.
  const ungrouped = results.filter(
    (service) => !service.category || !knownCategoryIds.has(service.category.id),
  );

  return (
    <Section
      id="services"
      title="Services"
      description="Pick two or more different services and 10% comes off automatically at checkout."
    >
      {groups.length === 0 ? (
        <ServiceGrid services={results} titleTag="h3" />
      ) : (
        <div className="space-y-12">
          {groups.map((group) => (
            <div key={group.id}>
              <h3 className="text-gold-400 text-xs tracking-[0.2em] uppercase">
                {group.name}
              </h3>
              <div className="mt-5">
                <ServiceGrid services={group.items} titleTag="h4" />
              </div>
            </div>
          ))}
          {ungrouped.length > 0 ? (
            <div>
              <h3 className="text-gold-400 text-xs tracking-[0.2em] uppercase">
                More services
              </h3>
              <div className="mt-5">
                <ServiceGrid services={ungrouped} titleTag="h4" />
              </div>
            </div>
          ) : null}
        </div>
      )}
    </Section>
  );
}
