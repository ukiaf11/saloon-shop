import type { Metadata, Viewport } from "next";
import { Fraunces, Nunito } from "next/font/google";

import { SALON_NAME } from "@/lib/site";

import "./globals.css";

// Fraunces is variable on a SOFT axis that rounds its serifs; globals.css turns
// it up so headings sit naturally beside clay surfaces. Nunito's rounded
// terminals carry the same softness into body text.
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display-loaded",
  display: "swap",
  axes: ["SOFT", "WONK", "opsz"],
});

const nunito = Nunito({
  subsets: ["latin"],
  variable: "--font-body-loaded",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: `${SALON_NAME} — Premium Grooming & Daily Lucky Slots`,
    template: `%s | ${SALON_NAME}`,
  },
  description:
    "Premium grooming with a daily lucky slot campaign. Book hair cutting, shaving and face massage, save 10% on two or more services, and pay securely online.",
  openGraph: {
    type: "website",
    siteName: SALON_NAME,
    title: `${SALON_NAME} — Premium Grooming & Daily Lucky Slots`,
    description:
      "Save 10% on two or more services and enter the daily lucky slot campaign.",
  },
  // Mirrors robots.ts: a preview build carries a page-level noindex too, since
  // a crawler that reached a URL directly would never see robots.txt.
  robots:
    process.env.NEXT_PUBLIC_NOINDEX === "1"
      ? { index: false, follow: false }
      : { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#f3e9df",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-IN" className={`${fraunces.variable} ${nunito.variable}`}>
      <body className="text-ink min-h-dvh antialiased">
        <a
          href="#main"
          className="focus:clay-btn sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-5 focus:py-2.5 focus:font-semibold"
        >
          Skip to content
        </a>
        {/* The public site's chrome (navbar, footer, cart) lives in the (site)
            group's layout, so the owner panel under /admin gets none of it. */}
        {children}
      </body>
    </html>
  );
}
