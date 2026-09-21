import type { MetadataRoute } from "next";

// Required by `output: "export"` (the GitHub Pages build): without it Next
// treats this route handler as dynamic and refuses to export. Harmless for the
// standalone build, where the contents are static anyway.
export const dynamic = "force-static";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  // A preview deployment (e.g. the GitHub Pages fallback) must not be indexed:
  // it cannot take a booking, and letting it rank would both mislead customers
  // and compete with the real site for the salon's own name.
  if (process.env.NEXT_PUBLIC_NOINDEX === "1") {
    return { rules: [{ userAgent: "*", disallow: "/" }] };
  }

  return {
    rules: [
      // The admin surface, personal booking pages and opaque coupon URLs must
      // never be indexed.
      { userAgent: "*", allow: "/", disallow: ["/admin", "/order", "/coupon/"] },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
