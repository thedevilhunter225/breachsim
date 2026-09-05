import type { Metadata } from "next";

import { InvitationAcceptanceForm } from "@/components/invitation-acceptance";

export const metadata: Metadata = {
  title: "Activate organization access",
  robots: { index: false, follow: false },
};

export default async function AcceptInvitePage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const resolved = await searchParams;
  const token = Array.isArray(resolved.token) ? resolved.token[0] : resolved.token;
  return <InvitationAcceptanceForm token={token ?? ""} />;
}
