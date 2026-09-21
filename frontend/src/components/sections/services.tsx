/**
 * The services section. A server component that hands the API payload to the
 * client-side browser, which owns the category filter.
 */

import type { ServiceList } from "@/types/api";

import { Section } from "./section";
import { ServiceBrowser } from "./service-browser";

export function ServicesSection({ services }: { services: ServiceList }) {
  const { categories, results } = services;

  // The section keeps its anchor even when empty: #services is a navbar link
  // and a dead anchor is worse than a quiet line of text.
  if (results.length === 0) {
    return (
      <Section id="services" eyebrow="Our services" title="What we do best">
        <p className="clay text-ink-soft p-8">
          Our service list is being updated. Call the salon and we will walk you through
          it.
        </p>
      </Section>
    );
  }

  return (
    <Section
      id="services"
      eyebrow="Our services"
      title="What we do best"
      description="Pick two or more different services and 10% comes off automatically at checkout."
    >
      <ServiceBrowser categories={categories} services={results} />
    </Section>
  );
}
