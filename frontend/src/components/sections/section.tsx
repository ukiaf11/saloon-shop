/**
 * Shared shell for every public section.
 *
 * It owns the three things that must not drift between sections: the anchor id
 * the navbar links to, the <h2> that keeps the page's heading order unbroken
 * (h1 lives in the hero), and the vertical rhythm.
 */

import type { ReactNode } from "react";

import { Reveal } from "@/components/reveal";

export function Section({
  id,
  title,
  eyebrow,
  description,
  align = "left",
  revealChildren = true,
  children,
}: {
  id: string;
  title: string;
  /** A short clay chip above the heading. */
  eyebrow?: string;
  description?: string;
  align?: "left" | "center";
  /** Off when the children stagger their own reveals (cards, steps). */
  revealChildren?: boolean;
  children: ReactNode;
}) {
  const centered = align === "center";
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      // scroll-mt-28 clears the floating navbar, so jumping to an anchor does
      // not park the heading underneath it.
      className="scroll-mt-28 px-4 py-10 sm:py-14"
    >
      <div className="mx-auto max-w-6xl">
        <Reveal className={centered ? "mx-auto max-w-2xl text-center" : "max-w-2xl"}>
          {eyebrow ? (
            <p className="clay-sm text-primary inline-block px-4 py-1.5 text-xs font-bold tracking-[0.14em] uppercase">
              {eyebrow}
            </p>
          ) : null}
          <h2
            id={`${id}-heading`}
            className={`font-display text-ink text-3xl leading-tight sm:text-4xl ${eyebrow ? "mt-4" : ""}`}
          >
            {title}
          </h2>
          {description ? (
            <p className="text-ink-soft mt-3 text-base sm:text-lg">{description}</p>
          ) : null}
        </Reveal>
        {revealChildren ? (
          <Reveal delay={120} className="mt-8 sm:mt-10">
            {children}
          </Reveal>
        ) : (
          <div className="mt-8 sm:mt-10">{children}</div>
        )}
      </div>
    </section>
  );
}
