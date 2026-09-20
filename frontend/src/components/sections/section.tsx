/**
 * Shared shell for every public section.
 *
 * It owns the three things that must not drift between sections: the anchor id
 * the navbar links to, the <h2> that keeps the page's heading order unbroken
 * (h1 lives in the hero), and the vertical rhythm.
 */

import type { ReactNode } from "react";

export function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      // scroll-mt-16 clears the 4rem sticky navbar, so jumping to an anchor
      // does not park the heading underneath it.
      className="border-ink-800 scroll-mt-16 border-t px-4 py-14 sm:py-16"
    >
      <div className="mx-auto max-w-6xl">
        <h2
          id={`${id}-heading`}
          className="text-ivory-50 font-[family-name:var(--font-display-loaded)] text-2xl sm:text-3xl"
        >
          {title}
        </h2>
        {description ? (
          <p className="text-ivory-500 mt-3 max-w-2xl text-sm">{description}</p>
        ) : null}
        <div className="mt-8">{children}</div>
      </div>
    </section>
  );
}
