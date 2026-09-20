import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      // The admin surface and opaque coupon URLs must never be indexed.
      { userAgent: "*", allow: "/", disallow: ["/admin", "/coupon/"] },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
