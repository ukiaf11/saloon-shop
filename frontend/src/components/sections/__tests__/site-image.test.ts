import { describe, expect, it } from "vitest";

import { isOptimizable } from "../site-image";

/**
 * This predicate decides which hosts the Next image optimizer will fetch from.
 * A host that passes here but is missing from next.config.ts throws at render;
 * a host that passes and should not is an SSRF surface. Both directions matter.
 */
describe("isOptimizable", () => {
  it("accepts paths we serve ourselves", () => {
    expect(isOptimizable("/logo.png")).toBe(true);
    expect(isOptimizable("/media/gallery/a.webp")).toBe(true);
  });

  it("accepts the local API's media path during development", () => {
    expect(isOptimizable("http://localhost:8000/media/gallery/a.png")).toBe(true);
    expect(isOptimizable("http://127.0.0.1:8000/media/gallery/a.png")).toBe(true);
  });

  it("rejects the local API outside its media path", () => {
    // Narrow to /media/ so the optimizer can never be pointed at an API route.
    expect(isOptimizable("http://localhost:8000/api/v1/salon")).toBe(false);
  });

  it("rejects other hosts and ports", () => {
    expect(isOptimizable("http://localhost:9999/media/a.png")).toBe(false);
    expect(isOptimizable("https://evil.example/media/a.png")).toBe(false);
    expect(isOptimizable("http://169.254.169.254/latest/meta-data")).toBe(false);
  });

  it("rejects malformed input instead of throwing", () => {
    expect(isOptimizable("not a url")).toBe(false);
    expect(isOptimizable("")).toBe(false);
  });
});
