import type { Metadata } from "next";

import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Promotion Rules" };

export default function Page() {
  return <LegalPage slug="promotion-rules" fallbackTitle="Promotion Rules" />;
}
