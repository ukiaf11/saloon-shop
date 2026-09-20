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
import { describe, expect, it } from "vitest";

import type { BusinessHour, GalleryImage, Service, ServiceList } from "@/types/api";

import { FaqSection } from "../faq";
import { GallerySection } from "../gallery";
import { OpeningHoursSection } from "../opening-hours";
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
      <ServicesSection
        services={serviceList({ results: [service({ price_paise: 123456789 })] })}
      />,
    );
    expect(screen.getByText("₹12,34,567.89")).toBeTruthy();
  });

  it("renders duration in hours once it passes an hour", () => {
    render(
      <ServicesSection
        services={serviceList({ results: [service({ duration_minutes: 90 })] })}
      />,
    );
    expect(screen.getByText("1 hr 30 min")).toBeTruthy();
  });

  it("groups under category headings and keeps heading order h2 -> h3 -> h4", () => {
    const { container } = render(<ServicesSection services={serviceList()} />);
    expect(container.querySelector("h2")?.textContent).toBe("Services");
    expect(container.querySelector("h3")?.textContent).toBe("Hair");
    expect(container.querySelector("h4")?.textContent).toBe("Hair Cutting");
  });

  it("promotes service names to h3 when there are no categories", () => {
    const { container } = render(
      <ServicesSection
        services={serviceList({ categories: [], results: [service({ category: null })] })}
      />,
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
    render(<ServicesSection services={serviceList({ results: [service(), orphan] })} />);
    expect(screen.getByText("Head Massage")).toBeTruthy();
    expect(screen.getByText("More services")).toBeTruthy();
  });

  it("leaves the Add control inert until Phase 3 wires selection", () => {
    render(<ServicesSection services={serviceList()} />);
    const add = screen.getByRole("button", { name: "Add Hair Cutting" });
    expect((add as HTMLButtonElement).disabled).toBe(true);
  });

  it("keeps the #services anchor alive when the catalogue is empty", () => {
    const { container } = render(
      <ServicesSection services={{ categories: [], results: [] }} />,
    );
    expect(container.querySelector("#services")).not.toBeNull();
    expect(container.querySelector("ul")).toBeNull();
  });
});

describe("OpeningHoursSection", () => {
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
    render(<OpeningHoursSection hours={week} />);
    expect(screen.getByText("10:00 AM – 9:00 PM")).toBeTruthy();
  });

  it("says Closed in words, not only in colour", () => {
    render(<OpeningHoursSection hours={week} />);
    expect(screen.getByText("Closed")).toBeTruthy();
  });

  it("treats a day with no times as closed even when the flag disagrees", () => {
    render(
      <OpeningHoursSection
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
    const { container } = render(<OpeningHoursSection hours={[week[1], week[0]]} />);
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
