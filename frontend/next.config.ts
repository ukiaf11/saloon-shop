import type { NextConfig } from "next";

/**
 * Two build targets.
 *
 * `standalone` (default) is the real one: a Node server that renders on demand,
 * revalidates on a tag, and optimizes images.
 *
 * `export` produces a folder of static files for GitHub Pages, which is the
 * fallback host when no application server is available. Pages cannot run
 * Node, so that build loses on-demand rendering, tag revalidation and the image
 * optimizer, and whatever the API returned at BUILD time is frozen into the
 * HTML. It is a preview of the marketing page, not the product -- checkout,
 * the lucky campaign and the admin panel all need the Django API and a server.
 */
const isStaticExport = process.env.NEXT_OUTPUT_EXPORT === "1";
const onVercel = process.env.VERCEL === "1";

// NEXT_PUBLIC_API_BASE_URL is inlined into the browser bundle at build time.
// On Vercel a build that starts before the variable exists would silently ship
// a bundle calling localhost:8000; failing the build is the better outcome.
if (onVercel && !process.env.NEXT_PUBLIC_API_BASE_URL?.trim()) {
  throw new Error("NEXT_PUBLIC_API_BASE_URL must be set for a Vercel build.");
}

// GitHub project pages serve from /<repo>, so every asset and link needs that
// prefix. A user/org page (<user>.github.io) serves from the root and must
// leave this empty.
const basePath = process.env.NEXT_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  // Vercel builds Next natively; "standalone" is for self-hosting in Docker.
  output: isStaticExport ? "export" : onVercel ? undefined : "standalone",
  reactStrictMode: true,
  poweredByHeader: false,

  ...(basePath ? { basePath, assetPrefix: basePath } : {}),

  // Pages serves /about as /about/index.html, so emit directory-style routes.
  ...(isStaticExport ? { trailingSlash: true } : {}),

  images: {
    formats: ["image/avif", "image/webp"],
    // The optimizer is a server feature. A static export must ship the original
    // bytes instead, or next/image throws at build time.
    unoptimized: isStaticExport,
    // Next refuses to optimize an image whose host resolves to a private IP,
    // which is an SSRF protection worth keeping. In local development the API
    // *is* on localhost, so without this the dev site silently loses AVIF/WebP
    // and srcset and stops resembling production. Development only -- the
    // guard stays on in production, where media is served from object storage
    // over a public hostname.
    dangerouslyAllowLocalIP: process.env.NODE_ENV !== "production",
    // The API serves uploaded images from its own origin, so it must be
    // allowlisted or next/image refuses them and SiteImage falls back to a
    // plain <img> (losing AVIF/WebP and srcset). The production object-storage
    // host is added here when it is provisioned.
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "8000", pathname: "/media/**" },
      { protocol: "http", hostname: "127.0.0.1", port: "8000", pathname: "/media/**" },
      ...(process.env.NEXT_PUBLIC_MEDIA_HOSTNAME
        ? [
            {
              protocol: "https" as const,
              hostname: process.env.NEXT_PUBLIC_MEDIA_HOSTNAME,
              pathname: "/**",
            },
          ]
        : []),
    ],
  },

  // headers() has no effect on a static export -- GitHub Pages sends its own
  // and there is no server to add ours. The security headers below therefore
  // apply to the standalone build only; on Pages they must come from the CDN
  // in front of it, or from meta tags.
  ...(isStaticExport
    ? {}
    : {
        async headers() {
          // Baseline security headers. The full nonce-based CSP, which must
          // allow the Razorpay checkout script and frame, lands in Phase 9
          // alongside the payment integration -- see IMPLEMENTATION_PLAN.md.
          return [
            {
              source: "/:path*",
              headers: [
                { key: "X-Content-Type-Options", value: "nosniff" },
                { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                { key: "X-Frame-Options", value: "DENY" },
                {
                  key: "Permissions-Policy",
                  // Camera stays enabled for the admin QR scanner (Phase 8).
                  value: "geolocation=(), microphone=(), payment=(), camera=(self)",
                },
              ],
            },
          ];
        },
      }),
};

export default nextConfig;
