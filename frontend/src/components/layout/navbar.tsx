"use client";

import Link from "next/link";
import { useState } from "react";

import { ScissorsArt } from "@/components/clay/clay-art";

// "/#…" rather than "#…": the navbar also renders on /order, /credits and the
// policy pages, where a bare hash is a dead link. On the home page itself the
// path is unchanged, so the browser still just scrolls.
const LINKS = [
  { href: "/#services", label: "Services" },
  { href: "/#offers", label: "How it works" },
  { href: "/#campaign", label: "Lucky offer" },
  { href: "/#contact", label: "Contact" },
];

/**
 * A floating clay pill rather than a full-width bar: it reads as an object
 * resting over the page, which is the whole clay idiom, and it keeps the
 * sticky header visually light on a small screen.
 */
export function Navbar({ salonName }: { salonName: string }) {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 px-3 pt-3 sm:px-4 sm:pt-4">
      <nav
        aria-label="Primary"
        className="clay mx-auto flex h-16 max-w-6xl items-center justify-between rounded-full! px-3 pr-3 pl-4 sm:px-6"
      >
        {/* The logo goes home, from any page -- a bare "#main" only scrolled. */}
        <Link href="/" className="flex min-h-11 items-center gap-2.5">
          <span className="bg-peach flex h-10 w-10 items-center justify-center rounded-full">
            <ScissorsArt size={30} />
          </span>
          <span className="font-display text-ink text-lg sm:text-xl">{salonName}</span>
        </Link>

        <ul className="hidden items-center gap-1 lg:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="text-ink-soft hover:text-ink hover:bg-clay-deep rounded-full px-4 py-2 text-sm font-semibold transition-colors"
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-2">
          <Link
            href="/#services"
            className="clay-btn hidden min-h-11 items-center px-5 text-sm font-bold sm:inline-flex"
          >
            Book now
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="mobile-menu"
            className="clay-btn-soft flex h-11 w-11 items-center justify-center lg:hidden"
          >
            <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <path
                d={open ? "M6 6l12 12M18 6L6 18" : "M4 7h16M4 12h16M4 17h16"}
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </nav>

      {open && (
        <div id="mobile-menu" className="clay mx-auto mt-3 max-w-6xl p-3 lg:hidden">
          <ul>
            {LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="text-ink hover:bg-clay-deep block rounded-2xl px-4 py-3 font-semibold"
                >
                  {link.label}
                </Link>
              </li>
            ))}
            <li className="pt-2">
              <Link
                href="/#services"
                onClick={() => setOpen(false)}
                className="clay-btn block px-5 py-3 text-center font-bold"
              >
                Book now
              </Link>
            </li>
          </ul>
        </div>
      )}
    </header>
  );
}
