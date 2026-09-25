/**
 * What a static image import resolves to under vitest.
 *
 * The real bundler turns `import photo from "x.webp"` into StaticImageData;
 * without this stub it resolves to a bare string and next/image throws over
 * the missing blurDataURL, failing every test that renders a photo.
 */
const stub = {
  src: "/static-image-stub.webp",
  height: 550,
  width: 800,
  blurDataURL:
    "data:image/webp;base64,UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAQAcJaQAA3AA/v3AgAA=",
};

export default stub;
