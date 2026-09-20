/**
 * JSON-LD builders for the public site (schema.org).
 *
 * These return plain objects; a component serialises them into a
 * <script type="application/ld+json"> tag. Keeping the shape-building here
 * means the markup can be unit-tested without rendering anything.
 *
 * Only data the API already publishes is emitted. Structured data that
 * contradicts the visible page is a manual-action risk with search engines, so
 * nothing here invents a rating, a price range or an address component.
 */

import type { BusinessHour, Faq, Salon, Service } from "@/types/api";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/**
 * Indexed by day_of_week (0 = Monday). Derived locally rather than from the
 * API's `day_name`, because schema.org requires these exact English tokens and
 * `day_name` is display text the owner may localise.
 */
const SCHEMA_DAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

/** schema.org's convention for "closed on this day". */
const CLOSED_ALL_DAY = { opens: "00:00", closes: "00:00" } as const;

export type OpeningHoursSpecification = {
  "@type": "OpeningHoursSpecification";
  dayOfWeek: string;
  opens: string;
  closes: string;
};

export type PostalAddress = {
  "@type": "PostalAddress";
  streetAddress: string;
  addressCountry: "IN";
};

export type LocalBusinessJsonLd = {
  "@context": "https://schema.org";
  "@type": "HairSalon";
  name: string;
  url: string;
  telephone?: string;
  address?: PostalAddress;
  openingHoursSpecification: OpeningHoursSpecification[];
  image?: string[];
  email?: string;
  hasMap?: string;
  sameAs?: string[];
};

export type ServiceJsonLd = {
  "@context": "https://schema.org";
  "@type": "Service";
  name: string;
  description: string;
  url: string;
  provider: { "@type": "HairSalon"; name: string; telephone?: string; url: string };
  offers: {
    "@type": "Offer";
    priceCurrency: "INR";
    price: string;
    availability: "https://schema.org/InStock";
    priceSpecification: {
      "@type": "UnitPriceSpecification";
      priceCurrency: "INR";
      price: string;
    };
  };
  serviceType?: string;
  image?: string;
};

export type FaqPageJsonLd = {
  "@context": "https://schema.org";
  "@type": "FAQPage";
  mainEntity: {
    "@type": "Question";
    name: string;
    acceptedAnswer: { "@type": "Answer"; text: string };
  }[];
};

/**
 * Render integer paise as a schema.org decimal rupee string: 30000 -> "300.00".
 *
 * The stored value is paise, not rupees -- dividing by 100 in floating point
 * would eventually emit "299.99999999999994" into the markup, so the rupee and
 * paise parts are split with integer arithmetic. Deliberately not exported:
 * `formatInr` in lib/money.ts is the display formatter, and a second exported
 * money function is a second thing to keep in sync.
 */
function rupeesFromPaise(paise: number): string {
  if (!Number.isInteger(paise)) {
    throw new Error(`rupeesFromPaise expects integer paise, got ${paise}`);
  }
  const sign = paise < 0 ? "-" : "";
  const absolute = Math.abs(paise);
  const rupees = Math.floor(absolute / 100);
  const remainder = absolute % 100;
  return `${sign}${rupees}.${String(remainder).padStart(2, "0")}`;
}

function openingHours(hours: BusinessHour[]): OpeningHoursSpecification[] {
  return hours.map((hour) => {
    const dayOfWeek = SCHEMA_DAY_NAMES[hour.day_of_week] ?? hour.day_name;
    // A day missing either time is treated as closed whatever the flag says --
    // emitting `opens: null` would invalidate the whole block.
    if (hour.is_closed || !hour.open_time || !hour.close_time) {
      return { "@type": "OpeningHoursSpecification", dayOfWeek, ...CLOSED_ALL_DAY };
    }
    return {
      "@type": "OpeningHoursSpecification",
      dayOfWeek,
      opens: hour.open_time,
      closes: hour.close_time,
    };
  });
}

export function localBusinessJsonLd(
  salon: Salon,
  options: { siteUrl?: string; images?: string[] } = {},
): LocalBusinessJsonLd {
  const { siteUrl = SITE_URL, images = [] } = options;
  const socials = [
    salon.content.social_links.instagram,
    salon.content.social_links.facebook,
  ].filter((link): link is string => Boolean(link));

  return {
    "@context": "https://schema.org",
    "@type": "HairSalon",
    name: salon.name,
    url: siteUrl,
    // Omitted rather than null when unset: schema.org consumers treat an
    // explicit null as a malformed value, an absent key as simply unknown.
    ...(salon.phone ? { telephone: salon.phone } : {}),
    ...(salon.address
      ? {
          address: {
            "@type": "PostalAddress" as const,
            // The backend stores one free-text address line, so locality and
            // postal code would have to be guessed by splitting it. Better one
            // accurate field than three invented ones.
            streetAddress: salon.address,
            addressCountry: "IN" as const,
          },
        }
      : {}),
    openingHoursSpecification: openingHours(salon.business_hours),
    ...(images.length > 0 ? { image: images } : {}),
    ...(salon.email ? { email: salon.email } : {}),
    ...(salon.maps_url ? { hasMap: salon.maps_url } : {}),
    ...(socials.length > 0 ? { sameAs: socials } : {}),
  };
}

export function serviceJsonLd(
  service: Service,
  salon: Salon,
  options: { siteUrl?: string } = {},
): ServiceJsonLd {
  const { siteUrl = SITE_URL } = options;
  // price_paise is integer paise; schema.org wants rupees with two decimals.
  const price = rupeesFromPaise(service.price_paise);

  return {
    "@context": "https://schema.org",
    "@type": "Service",
    name: service.name,
    description: service.description,
    url: `${siteUrl}/#services`,
    provider: {
      "@type": "HairSalon",
      name: salon.name,
      ...(salon.phone ? { telephone: salon.phone } : {}),
      url: siteUrl,
    },
    offers: {
      "@type": "Offer",
      priceCurrency: "INR",
      price,
      availability: "https://schema.org/InStock",
      // No valueAddedTaxIncluded: GST treatment is still an open decision
      // (REQUIREMENTS.md 8.4), and asserting either way would be a guess.
      priceSpecification: {
        "@type": "UnitPriceSpecification",
        priceCurrency: "INR",
        price,
      },
    },
    ...(service.category ? { serviceType: service.category.name } : {}),
    ...(service.image_url ? { image: service.image_url } : {}),
  };
}

export function faqJsonLd(faqs: Faq[]): FaqPageJsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: { "@type": "Answer", text: faq.answer },
    })),
  };
}
