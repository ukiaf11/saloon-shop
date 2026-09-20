import { describe, expect, it } from "vitest";

import { faqJsonLd, localBusinessJsonLd, serviceJsonLd } from "../structured-data";
import type { BusinessHour, Faq, Salon, Service } from "@/types/api";

const DAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

/** Mon-Sat 10:00-21:00, closed Sunday -- the salon's real shape. */
function businessHours(): BusinessHour[] {
  return DAY_NAMES.map((day_name, index) => {
    const closed = index === 6;
    return {
      day_of_week: index,
      day_name,
      open_time: closed ? null : "10:00",
      close_time: closed ? null : "21:00",
      is_closed: closed,
    };
  });
}

function salon(overrides: Partial<Salon> = {}): Salon {
  return {
    name: "Upendra Salon",
    slug: "upendra-salon",
    timezone: "Asia/Kolkata",
    currency: "INR",
    address: "12 MG Road, Indore",
    phone: "+919000000000",
    whatsapp: "+919000000000",
    email: "hello@example.com",
    maps_url: "https://maps.google.com/?q=upendra-salon",
    business_hours: businessHours(),
    content: {
      hero_eyebrow: "Premium grooming. Daily rewards.",
      hero_heading: "Har Din 5 Lucky Slots",
      hero_subheading: "Free for the day's lucky slots.",
      why_choose_us: [{ title: "Trained stylists", body: "..." }],
      social_links: { instagram: "https://instagram.com/x", facebook: null },
    },
    ...overrides,
  };
}

function service(overrides: Partial<Service> = {}): Service {
  return {
    id: "7f2f2b0a-1c4f-4a1e-9a0e-3f0f2b0a1c4f",
    name: "Hair Cutting",
    slug: "hair-cutting",
    description: "Precision cut and styling.",
    price_paise: 30000,
    duration_minutes: 30,
    image_url: "https://cdn.example.com/hair-cutting.webp",
    is_featured: true,
    display_order: 1,
    category: { id: "1c4f2b0a-7f2f-4a1e-9a0e-3f0f2b0a1c4f", name: "Hair", slug: "hair" },
    ...overrides,
  };
}

describe("serviceJsonLd price rendering", () => {
  it("renders whole-rupee paise with two decimals", () => {
    const jsonLd = serviceJsonLd(service({ price_paise: 30000 }), salon());
    expect(jsonLd.offers.price).toBe("300.00");
    expect(jsonLd.offers.priceSpecification.price).toBe("300.00");
    expect(jsonLd.offers.priceCurrency).toBe("INR");
  });

  it("keeps a non-zero paise remainder, zero-padded", () => {
    expect(serviceJsonLd(service({ price_paise: 30050 }), salon()).offers.price).toBe(
      "300.50",
    );
    expect(serviceJsonLd(service({ price_paise: 30005 }), salon()).offers.price).toBe(
      "300.05",
    );
    expect(serviceJsonLd(service({ price_paise: 99 }), salon()).offers.price).toBe(
      "0.99",
    );
    expect(serviceJsonLd(service({ price_paise: 0 }), salon()).offers.price).toBe("0.00");
  });

  it("does not drift on amounts where float division would", () => {
    // 1_23_456.78 -- the kind of value that exposes a paise / 100 float bug.
    expect(serviceJsonLd(service({ price_paise: 12345678 }), salon()).offers.price).toBe(
      "123456.78",
    );
  });

  it("rejects non-integer paise, which would mean float money upstream", () => {
    expect(() => serviceJsonLd(service({ price_paise: 300.5 }), salon())).toThrow();
  });

  it("omits optional fields rather than emitting nulls", () => {
    const jsonLd = serviceJsonLd(service({ category: null, image_url: null }), salon());
    expect(jsonLd.serviceType).toBeUndefined();
    expect(jsonLd.image).toBeUndefined();
    expect(JSON.stringify(jsonLd)).not.toContain("null");
  });
});

describe("localBusinessJsonLd opening hours", () => {
  it("maps every day to a schema.org specification in Monday-first order", () => {
    const spec = localBusinessJsonLd(salon()).openingHoursSpecification;
    expect(spec).toHaveLength(7);
    expect(spec.map((entry) => entry.dayOfWeek)).toEqual(DAY_NAMES);
    expect(spec[0]).toEqual({
      "@type": "OpeningHoursSpecification",
      dayOfWeek: "Monday",
      opens: "10:00",
      closes: "21:00",
    });
  });

  it("renders a closed day as 00:00-00:00, never as null times", () => {
    const sunday = localBusinessJsonLd(salon()).openingHoursSpecification[6];
    expect(sunday).toEqual({
      "@type": "OpeningHoursSpecification",
      dayOfWeek: "Sunday",
      opens: "00:00",
      closes: "00:00",
    });
  });

  it("treats a day with missing times as closed even if the flag says open", () => {
    const hours = businessHours();
    hours[2] = { ...hours[2], is_closed: false, open_time: null, close_time: null };
    const wednesday = localBusinessJsonLd(salon({ business_hours: hours }))
      .openingHoursSpecification[2];
    expect(wednesday.opens).toBe("00:00");
    expect(wednesday.closes).toBe("00:00");
  });

  it("uses schema.org day names, not the API's display labels", () => {
    const hours = businessHours();
    hours[0] = { ...hours[0], day_name: "Somvaar" };
    const spec = localBusinessJsonLd(
      salon({ business_hours: hours }),
    ).openingHoursSpecification;
    expect(spec[0].dayOfWeek).toBe("Monday");
  });

  it("carries the contact details and drops absent social links", () => {
    const jsonLd = localBusinessJsonLd(salon(), { siteUrl: "https://salon.example" });
    expect(jsonLd["@type"]).toBe("HairSalon");
    expect(jsonLd.url).toBe("https://salon.example");
    expect(jsonLd.telephone).toBe("+919000000000");
    expect(jsonLd.address).toEqual({
      "@type": "PostalAddress",
      streetAddress: "12 MG Road, Indore",
      addressCountry: "IN",
    });
    expect(jsonLd.hasMap).toBe("https://maps.google.com/?q=upendra-salon");
    // facebook is null in the fixture and must not appear as an empty entry.
    expect(jsonLd.sameAs).toEqual(["https://instagram.com/x"]);
  });

  it("omits image when the caller passes none", () => {
    expect(localBusinessJsonLd(salon()).image).toBeUndefined();
    expect(
      localBusinessJsonLd(salon(), { images: ["https://cdn/x.webp"] }).image,
    ).toEqual(["https://cdn/x.webp"]);
  });
});

describe("faqJsonLd", () => {
  const faqs: Faq[] = [
    {
      id: "aaaaaaaa-1c4f-4a1e-9a0e-3f0f2b0a1c4f",
      question: "How does the lucky slot work?",
      answer: "Each day a fixed number of slots are lucky.",
      display_order: 1,
    },
    {
      id: "bbbbbbbb-1c4f-4a1e-9a0e-3f0f2b0a1c4f",
      question: "Is the discount automatic?",
      answer: "Yes, for two or more distinct services.",
      display_order: 2,
    },
  ];

  it("builds an FAQPage with one Question per item, in order", () => {
    expect(faqJsonLd(faqs)).toEqual({
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: [
        {
          "@type": "Question",
          name: "How does the lucky slot work?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Each day a fixed number of slots are lucky.",
          },
        },
        {
          "@type": "Question",
          name: "Is the discount automatic?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Yes, for two or more distinct services.",
          },
        },
      ],
    });
  });

  it("still produces valid markup for an empty FAQ list", () => {
    expect(faqJsonLd([]).mainEntity).toEqual([]);
  });
});
