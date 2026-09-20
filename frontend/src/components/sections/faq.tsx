/**
 * FAQ accordion. Server component on purpose.
 *
 * <details>/<summary> is a native disclosure: keyboard operable, correctly
 * announced (HTML-AAM maps summary to a button whose expanded state the browser
 * keeps in sync), and it works before hydration. A hand-written aria-expanded
 * is deliberately absent -- React does not own the open state here, so any
 * value we wrote would be a lie the moment someone clicked. Reach for
 * "use client" + useState only if this ever needs single-open behaviour or
 * animated height.
 */

import type { Faq } from "@/types/api";

import { Section } from "./section";

export function FaqSection({ faqs }: { faqs: Faq[] }) {
  if (faqs.length === 0) return null;

  return (
    <Section id="faq" title="Frequently asked questions">
      <ul className="max-w-3xl space-y-3">
        {faqs.map((faq) => (
          <li key={faq.id}>
            <details className="group border-ink-700/60 bg-ink-900 rounded-card border">
              <summary className="text-ivory-50 flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-sm font-medium [&::-webkit-details-marker]:hidden">
                {faq.question}
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                  className="text-gold-400 shrink-0 transition-transform group-open:rotate-180"
                >
                  <path
                    d="M6 9l6 6 6-6"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </summary>
              <p className="text-ivory-300 px-5 pb-4 text-sm leading-relaxed">
                {faq.answer}
              </p>
            </details>
          </li>
        ))}
      </ul>
    </Section>
  );
}
