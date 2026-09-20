import type { Metadata, Viewport } from "next";
import { Inter, Playfair_Display } from "next/font/google";

import { Footer } from "@/components/layout/footer";
import { Navbar } from "@/components/layout/navbar";

import "./globals.css";

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display-loaded",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body-loaded",
  display: "swap",
});

const SALON_NAME = "Upendra Salon";

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
  themeColor: "#0d0b0a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-IN" className={`${playfair.variable} ${inter.variable}`}>
      <body className="bg-ink-950 text-ivory-100 min-h-dvh antialiased">
        <a
          href="#main"
          className="focus:bg-gold-500 focus:text-ink-950 sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:px-4 focus:py-2"
        >
          Skip to content
        </a>
        <Navbar salonName={SALON_NAME} />
        <main id="main">{children}</main>
        <Footer salonName={SALON_NAME} />
      </body>
    </html>
  );
}
