/**
 * The one place that decides how a content image is rendered.
 *
 * next/image *throws* on a host that is not listed in `images.remotePatterns`,
 * which would take down the whole page rather than drop one picture. So the
 * rule is: a host we have allowlisted goes through the optimizer (AVIF/WebP,
 * srcset, lazy loading); anything else falls back to a plain <img>.
 *
 * `next.config.ts` allowlists the API origin for locally served media and, when
 * `NEXT_PUBLIC_MEDIA_HOSTNAME` is set, the production object-storage host. The
 * fallback therefore only triggers for an unexpected host -- it is a safety
 * net, not the normal path.
 *
 * Both branches carry explicit width/height, so the browser reserves the box
 * from the first paint either way and there is no layout shift.
 */

import Image from "next/image";

/**
 * Mirrors the allowlist in next.config.ts. Kept as a runtime check because
 * next/image's failure mode is a thrown error at render, and one bad image URL
 * from the CMS should not blank the marketing page.
 */
export function isOptimizable(src: string): boolean {
  if (src.startsWith("/")) return true;

  let url: URL;
  try {
    url = new URL(src);
  } catch {
    return false;
  }

  const mediaHost = process.env.NEXT_PUBLIC_MEDIA_HOSTNAME;
  if (mediaHost && url.protocol === "https:" && url.hostname === mediaHost) {
    return true;
  }

  const isLocalApi =
    url.protocol === "http:" &&
    (url.hostname === "localhost" || url.hostname === "127.0.0.1") &&
    url.port === "8000" &&
    url.pathname.startsWith("/media/");

  return isLocalApi;
}

export function SiteImage({
  src,
  alt,
  width,
  height,
  sizes,
  className,
}: {
  src: string;
  alt: string;
  width: number;
  height: number;
  sizes?: string;
  className?: string;
}) {
  if (isOptimizable(src)) {
    return (
      <Image
        src={src}
        alt={alt}
        width={width}
        height={height}
        sizes={sizes}
        className={className}
      />
    );
  }

  return (
    // Unrecognised host: the optimizer would throw, so serve it directly.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      loading="lazy"
      decoding="async"
      className={className}
    />
  );
}
