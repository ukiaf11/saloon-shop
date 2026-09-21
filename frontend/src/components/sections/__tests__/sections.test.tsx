/**
 * Render checks for the public sections.
 *
 * These components are synchronous server components, which makes them plain
 * functions of their props -- Testing Library can render them directly. The
 * cases here are the ones that would quietly ship wrong: a service dropping out
 * of the grid, a price rendered by hand, a closed day shown as open times, a
 * missing alt text.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CartProvider } from "@/lib/cart";
import { describe, expect, it } from "vitest";

import type { BusinessHour, GalleryImage, Service, ServiceList } from "@/types/api";

import { FaqSection } from "../faq";
import { GallerySection } from "../gallery";
import { OpeningHoursCard } from "../opening-hours";
import { ServicesSection } from "../services";
import { TestimonialsSection } from "../testimonials";

const HAIR_CATEGORY = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Hair",
  slug: "hair",
};

function service(overrides: Partial<Service> = {}): Service {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    name: "Hair Cutting",
    slug: "hair-cutting",
    description: "Precision cut and styling.",
    price_paise: 30000,
    duration_minutes: 30,
    image_url: null,
    is_featured: false,
    display_order: 1,
    category: HAIR_CATEGORY,
    ...overrides,
  };
}

function serviceList(overrides: Partial<ServiceList> = {}): ServiceList {
  return {
    categories: [{ ...HAIR_CATEGORY, display_order: 1 }],
    results: [service()],
    ...overrides,
  };
}

describe("ServicesSection", () => {
  it("renders the price through formatInr, never a hand-rolled one", () => {
    render(
      <CartProvider>
        <ServicesSection
          services={serviceList({ results: [service({ price_paise: 123456789 })] })}
        />
      </CartProvider>,
    );
    expect(screen.getByText("₹12,34,567.89")).toBeTruthy();
  });

  it("renders duration in hours once it passes an hour", () => {
    render(
      <CartProvider>
        <ServicesSection
          services={serviceList({ results: [service({ duration_minutes: 90 })] })}
        />
      </CartProvider>,
    );
    expect(screen.getByText("1 hr 30 min")).toBeTruthy();
  });

  it("keeps heading order h2 -> h3 with the category as a label, not a heading", () => {
    // Categories are a filter now, so a card's category is a label above its
    // name rather than a heading level between the section and the service.
    const { container } = render(
      <CartProvider>
        <ServicesSection services={serviceList()} />
      </CartProvider>,
    );
    expect(container.querySelector("h2")?.textContent).toBe("What we do best");
    expect(container.querySelector("h3")?.textContent).toBe("Hair Cutting");
    expect(container.querySelector("h4")).toBeNull();
  });

  it("promotes service names to h3 when there are no categories", () => {
    const { container } = render(
      <CartProvider>
        <ServicesSection
          services={serviceList({
            categories: [],
            results: [service({ category: null })],
          })}
        />
      </CartProvider>,
    );
    expect(container.querySelector("h3")?.textContent).toBe("Hair Cutting");
    expect(container.querySelector("h4")).toBeNull();
  });

  it("still renders a service whose category is missing from the category list", () => {
    const orphan = service({
      id: "33333333-3333-3333-3333-333333333333",
      name: "Head Massage",
      category: {
        id: "99999999-9999-9999-9999-999999999999",
        name: "Ghost",
        slug: "ghost",
      },
    });
    render(
      <CartProvider>
        <ServicesSection services={serviceList({ results: [service(), orphan] })} />
      </CartProvider>,
    );
    expect(screen.getByText("Head Massage")).toBeTruthy();
    expect(screen.getByText("More services")).toBeTruthy();
  });

  it("offers a working Add control that names the service it adds", () => {
    render(
      <CartProvider>
        <ServicesSection services={serviceList()} />
      </CartProvider>,
    );
    const add = screen.getByRole("button", { name: "Add Hair Cutting" });
    // Not disabled any more: Phase 3 wired selection. The service name stays in
    // the accessible name so the button is unambiguous out of context.
    expect((add as HTMLButtonElement).disabled).toBe(false);
  });

  it("keeps the #services anchor alive when the catalogue is empty", () => {
    const { container } = render(
      <CartProvider>
        <ServicesSection services={{ categories: [], results: [] }} />
      </CartProvider>,
    );
    expect(container.querySelector("#services")).not.toBeNull();
    expect(container.querySelector("ul")).toBeNull();
  });
});

describe("OpeningHoursCard", () => {
  const week: BusinessHour[] = [
    {
      day_of_week: 0,
      day_name: "Monday",
      open_time: "10:00",
      close_time: "21:00",
      is_closed: false,
    },
    {
      day_of_week: 6,
      day_name: "Sunday",
      open_time: null,
      close_time: null,
      is_closed: true,
    },
  ];

  it("converts 24-hour times without touching Date or Intl", () => {
    render(<OpeningHoursCard hours={week} />);
    expect(screen.getByText("10:00 AM – 9:00 PM")).toBeTruthy();
  });

  it("says Closed in words, not only in colour", () => {
    render(<OpeningHoursCard hours={week} />);
    expect(screen.getByText("Closed")).toBeTruthy();
  });

  it("treats a day with no times as closed even when the flag disagrees", () => {
    render(
      <OpeningHoursCard
        hours={[
          {
            day_of_week: 2,
            day_name: "Wednesday",
            open_time: null,
            close_time: null,
            is_closed: false,
          },
        ]}
      />,
    );
    expect(screen.getByText("Closed")).toBeTruthy();
  });

  it("prints the week in day order even if the payload is shuffled", () => {
    const { container } = render(<OpeningHoursCard hours={[week[1], week[0]]} />);
    const days = [...container.querySelectorAll("dt")].map((node) => node.textContent);
    expect(days).toEqual(["Monday", "Sunday"]);
  });
});

describe("GallerySection", () => {
  const image: GalleryImage = {
    id: "44444444-4444-4444-4444-444444444444",
    image_url: "https://cdn.example.com/salon-1.webp",
    alt_text: "Styling chair at the salon",
    caption: "Our main floor",
    display_order: 1,
    width: 1600,
    height: 1067,
  };

  it("uses the API alt text and reserves the box with the payload dimensions", () => {
    const { container } = render(<GallerySection images={[image]} />);
    const rendered = container.querySelector("img");
    expect(rendered?.getAttribute("alt")).toBe("Styling chair at the salon");
    expect(rendered?.getAttribute("width")).toBe("1600");
    expect(rendered?.getAttribute("height")).toBe("1067");
  });

  it("falls back to a 4:3 box when the dimensions are unknown", () => {
    const { container } = render(
      <GallerySection images={[{ ...image, width: null, height: null }]} />,
    );
    const rendered = container.querySelector("img");
    expect(rendered?.getAttribute("width")).toBe("1200");
    expect(rendered?.getAttribute("height")).toBe("900");
  });
});

describe("empty states", () => {
  it("renders nothing rather than an empty shell", () => {
    expect(render(<FaqSection faqs={[]} />).container.innerHTML).toBe("");
    expect(render(<TestimonialsSection testimonials={[]} />).container.innerHTML).toBe(
      "",
    );
  });

  it("shows no gallery at all rather than stock photos passed off as the salon", () => {
    // Filling an empty gallery with stock photography would present someone
    // else's salon as this one. The navbar does not link to #gallery, so an
    // absent section leaves no dead anchor.
    expect(render(<GallerySection images={[]} />).container.innerHTML).toBe("");
  });

  it("renders no hours card when the week is unknown", () => {
    expect(render(<OpeningHoursCard hours={[]} />).container.innerHTML).toBe("");
  });
});

describe("FaqSection", () => {
  it("uses a native disclosure so it works without JavaScript", () => {
    const { container } = render(
      <FaqSection
        faqs={[
          {
            id: "55555555-5555-5555-5555-555555555555",
            question: "How does the lucky slot work?",
            answer: "Each day a fixed number of slots is drawn in advance.",
            display_order: 1,
          },
        ]}
      />,
    );
    expect(container.querySelector("details > summary")?.textContent).toContain(
      "How does the lucky slot work?",
    );
  });
});

describe("TestimonialsSection", () => {
  it("exposes the rating as text, not only as stars", () => {
    render(
      <TestimonialsSection
        testimonials={[
          {
            id: "66666666-6666-6666-6666-666666666666",
            author_name: "Rahul S.",
            rating: 4,
            body: "Best haircut in town.",
            display_order: 1,
          },
        ]}
      />,
    );
    expect(screen.getByText("Rated 4 out of 5")).toBeTruthy();
  });
});

describe("ServiceBrowser filter", () => {
  const hair = { id: "c1c1c1c1-1111-4111-8111-111111111111", name: "Hair", slug: "hair" };
  const skin = { id: "c2c2c2c2-2222-4222-8222-222222222222", name: "Skin", slug: "skin" };
  const list = serviceList({
    categories: [
      { ...hair, display_order: 1 },
      { ...skin, display_order: 2 },
    ],
    results: [
      service({
        id: "a1a1a1a1-1111-4111-8111-111111111111",
        name: "Hair Cutting",
        category: hair,
      }),
      service({
        id: "a2a2a2a2-2222-4222-8222-222222222222",
        name: "Facial",
        slug: "facial",
        category: skin,
      }),
    ],
  });

  it("shows every service under All, and narrows on a category", async () => {
    const user = userEvent.setup();
    render(
      <CartProvider>
        <ServicesSection services={list} />
      </CartProvider>,
    );
    expect(screen.getByText("Hair Cutting")).toBeTruthy();
    expect(screen.getByText("Facial")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Skin" }));
    expect(screen.queryByText("Hair Cutting")).toBeNull();
    expect(screen.getByText("Facial")).toBeTruthy();
  });

  it("marks the active chip with aria-pressed", async () => {
    const user = userEvent.setup();
    render(
      <CartProvider>
        <ServicesSection services={list} />
      </CartProvider>,
    );
    const all = screen.getByRole("button", { name: "All" });
    const skinChip = screen.getByRole("button", { name: "Skin" });
    expect(all.getAttribute("aria-pressed")).toBe("true");

    await user.click(skinChip);
    expect(skinChip.getAttribute("aria-pressed")).toBe("true");
    expect(all.getAttribute("aria-pressed")).toBe("false");
  });

  it("announces the count rather than making the whole list live", async () => {
    const user = userEvent.setup();
    render(
      <CartProvider>
        <ServicesSection services={list} />
      </CartProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Hair" }));
    expect(screen.getByText("Showing 1 service")).toBeTruthy();
  });
});
