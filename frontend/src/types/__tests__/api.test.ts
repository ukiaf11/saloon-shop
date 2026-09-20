import { describe, expect, it } from "vitest";

import { salonContentSchema, socialLinksSchema } from "@/types/api";

/**
 * These payloads come from owner-edited JSONB rows. A strict schema turns one
 * careless CMS edit into a blank homepage, so the tolerance is deliberate and
 * worth pinning down.
 */
describe("socialLinksSchema", () => {
  it("accepts both links", () => {
    expect(
      socialLinksSchema.parse({ instagram: "https://ig", facebook: "https://fb" }),
    ).toEqual({ instagram: "https://ig", facebook: "https://fb" });
  });

  it("treats a missing key as an absent link rather than failing", () => {
    expect(socialLinksSchema.parse({ instagram: "https://ig" })).toEqual({
      instagram: "https://ig",
      facebook: null,
    });
  });

  it("accepts an entirely empty object", () => {
    expect(socialLinksSchema.parse({})).toEqual({ instagram: null, facebook: null });
  });

  it("accepts explicit nulls", () => {
    expect(socialLinksSchema.parse({ instagram: null, facebook: null })).toEqual({
      instagram: null,
      facebook: null,
    });
  });
});

describe("salonContentSchema", () => {
  it("survives a partial social_links row", () => {
    const parsed = salonContentSchema.parse({
      hero_eyebrow: "a",
      hero_heading: "b",
      hero_subheading: "c",
      why_choose_us: [{ title: "t", body: "b" }],
      social_links: { instagram: "https://ig" },
    });
    expect(parsed.social_links.facebook).toBeNull();
  });
});
