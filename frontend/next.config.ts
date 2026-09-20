import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output keeps the production image small.
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,

  images: {
    formats: ["image/avif", "image/webp"],
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

  async headers() {
    // Baseline security headers. The full nonce-based CSP, which must allow the
    // Razorpay checkout script and frame, lands in Phase 9 alongside the
    // payment integration -- see IMPLEMENTATION_PLAN.md.
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
};

export default nextConfig;
