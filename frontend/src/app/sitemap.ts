import type { MetadataRoute } from "next";

// Required by `output: "export"` (the GitHub Pages build): without it Next
// treats this route handler as dynamic and refuses to export. Harmless for the
// standalone build, where the contents are static anyway.
export const dynamic = "force-static";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = ["", "/terms", "/privacy", "/refunds", "/promotion-rules", "/contact"];
  return routes.map((route) => ({
    url: `${SITE_URL}${route}`,
    lastModified: new Date(),
    changeFrequency: route === "" ? "daily" : "monthly",
    priority: route === "" ? 1 : 0.4,
  }));
}
