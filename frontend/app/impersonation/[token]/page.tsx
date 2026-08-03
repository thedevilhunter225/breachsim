import type { Metadata } from "next";

import { SyntheticMediaSimulator } from "@/components/synthetic-media-simulator";

export const metadata: Metadata = {
  title: "New message",
  robots: { index: false, follow: false },
};

export default async function ImpersonationPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <SyntheticMediaSimulator token={token} />;
}
