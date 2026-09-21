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
    <Section id="faq" eyebrow="FAQ" title="Questions, answered" align="center">
      <ul className="mx-auto max-w-3xl space-y-4">
        {faqs.map((faq) => (
          <li key={faq.id}>
            <details className="group clay open:clay">
              <summary className="text-ink flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-5 font-bold [&::-webkit-details-marker]:hidden">
                {faq.question}
                <span
                  aria-hidden="true"
                  className="clay-btn-soft flex h-9 w-9 shrink-0 items-center justify-center transition-transform group-open:rotate-45"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M12 5v14M5 12h14"
                      stroke="currentColor"
                      strokeWidth="2.6"
                      strokeLinecap="round"
                    />
                  </svg>
                </span>
              </summary>
              <p className="text-ink-soft px-6 pb-6 leading-relaxed">{faq.answer}</p>
            </details>
          </li>
        ))}
      </ul>
    </Section>
  );
}
