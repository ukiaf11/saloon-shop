"use client";

/**
 * Scroll-triggered reveal that can never lose content.
 *
 * The CSS that hides `.reveal` elements applies only under
 * `html.reveal-armed` (see globals.css), and that class is added here, from
 * JS, inside the same task that immediately re-shows anything already in the
 * viewport. So: no JavaScript -> nothing is ever hidden; reduced motion ->
 * the media query never hides anything; JS present -> below-the-fold content
 * slides up as it scrolls in.
 *
 * No React state: the class flips are DOM-only, so re-renders never reset an
 * element to hidden, and the strict effect lint has nothing to object to.
 */

import { useEffect, useRef, type ReactNode } from "react";

export function Reveal({
  as = "div",
  delay = 0,
  className = "",
  children,
}: {
  /** The rendered element -- "li" when the reveal IS the grid item. */
  as?: "div" | "li" | "span";
  /** Stagger, in ms, applied via transition-delay. */
  delay?: number;
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    document.documentElement.classList.add("reveal-armed");

    // Already on screen (or IO unavailable): show it in the same task that
    // armed the hiding, so there is no hidden frame above the fold.
    if (
      typeof IntersectionObserver === "undefined" ||
      element.getBoundingClientRect().top < window.innerHeight
    ) {
      element.classList.add("reveal-shown");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal-shown");
            observer.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const shared = {
    className: `reveal ${className}`.trim(),
    style: delay
      ? ({ "--reveal-delay": `${delay}ms` } as React.CSSProperties)
      : undefined,
  };

  // Spelled out per tag: the ref prop is only lint-clean in literal JSX.
  if (as === "li") {
    return (
      <li ref={ref as React.Ref<HTMLLIElement>} {...shared}>
        {children}
      </li>
    );
  }
  if (as === "span") {
    return (
      <span ref={ref as React.Ref<HTMLSpanElement>} {...shared}>
        {children}
      </span>
    );
  }
  return (
    <div ref={ref as React.Ref<HTMLDivElement>} {...shared}>
      {children}
    </div>
  );
}
