import type { Metadata } from "next";

import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "Privacy" };

export default function Page() {
  return <LegalPage slug="privacy" fallbackTitle="Privacy" />;
}
