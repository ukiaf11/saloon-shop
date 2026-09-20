/**
 * Owner-authored selling points from SiteContent. Server component.
 */

import type { WhyChooseUsItem } from "@/types/api";

import { Section } from "./section";

export function WhyChooseUsSection({ items }: { items: WhyChooseUsItem[] }) {
  // The backend supplies a default list, so an empty array means the owner
  // cleared it deliberately. Respect that and render nothing.
  if (items.length === 0) return null;

  return (
    <Section id="why-us" title="Why choose us">
      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item, index) => (
          <li
            // Positional key: an owner-authored list with no stable id, rendered
            // once on the server and never reordered in the browser.
            key={`${index}-${item.title}`}
            className="border-ink-700/60 bg-ink-900 rounded-card border p-5"
          >
            <h3 className="text-ivory-50 text-base font-medium">{item.title}</h3>
            <p className="text-ivory-300 mt-2 text-sm leading-relaxed">{item.body}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}
