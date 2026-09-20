import type { Metadata } from "next";

import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Terms" };

export default function Page() {
  return <LegalPage slug="terms" fallbackTitle="Terms" />;
}
