import type { Metadata } from "next";

import { LocationSection } from "@/components/sections/location";
import { getSalon } from "@/lib/site-data";

export const metadata: Metadata = { title: "Contact" };

/** The same contact block as the home page, as its own linkable route. */
export default async function Page() {
  const salon = await getSalon();
  return <LocationSection salon={salon} />;
}
