import type { Metadata } from "next";

import { VoiceCallSimulator } from "@/components/voice-call-simulator";

export const metadata: Metadata = {
  title: "Incoming call",
  // The simulation must not be given away by a browser tab or a link preview.
  robots: { index: false, follow: false },
};

export default async function VoiceCallPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <VoiceCallSimulator token={token} />;
}
