"use client";

import { useState } from "react";

const LINKS = [
  { href: "#services", label: "Services" },
  { href: "#offers", label: "Offers" },
  { href: "#gallery", label: "Gallery" },
  { href: "#contact", label: "Contact" },
];

export function Navbar({ salonName }: { salonName: string }) {
  const [open, setOpen] = useState(false);

  return (
    <header className="border-ink-700/60 bg-ink-950/85 sticky top-0 z-40 border-b backdrop-blur">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4"
      >
        <a
          href="#main"
          className="text-ivory-50 font-[family-name:var(--font-display-loaded)] text-lg"
        >
          {salonName}
        </a>

        <ul className="hidden items-center gap-7 md:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="text-ivory-300 hover:text-gold-400 text-sm transition-colors"
              >
                {link.label}
              </a>
            </li>
          ))}
          <li>
            <a
              href="#services"
              className="bg-gold-500 text-ink-950 hover:bg-gold-400 rounded-full px-5 py-2 text-sm font-medium transition-colors"
            >
              Book Now
            </a>
          </li>
        </ul>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls="mobile-menu"
          className="text-ivory-100 rounded-md p-2 md:hidden"
        >
          <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d={open ? "M6 6l12 12M18 6L6 18" : "M4 7h16M4 12h16M4 17h16"}
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </nav>

      {open && (
        <div id="mobile-menu" className="border-ink-700/60 border-t md:hidden">
          <ul className="mx-auto max-w-6xl px-4 py-3">
            {LINKS.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="text-ivory-300 hover:text-gold-400 block py-3"
                >
                  {link.label}
                </a>
              </li>
            ))}
            <li className="pt-2 pb-1">
              <a
                href="#services"
                onClick={() => setOpen(false)}
                className="bg-gold-500 text-ink-950 block rounded-full px-5 py-2.5 text-center font-medium"
              >
                Book Now
              </a>
            </li>
          </ul>
        </div>
      )}
    </header>
  );
}
