"use client";

import { ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";

import { BrandLogo } from "@/components/brand-logo";
import { NavShell } from "@/components/nav-shell";
import { useSession } from "@/components/session-provider";

export function DashboardShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { ready, session, signOut } = useSession();

  useEffect(() => {
    if (ready && !session) {
      router.replace("/login");
    }
  }, [ready, router, session]);

  if (!ready || !session) {
    return (
      <div className="workspace-shell flex min-h-screen items-center justify-center px-4 py-10" role="status">
        <div className="flex items-center gap-4 px-6 py-5">
          <BrandLogo compact />
          <div className="text-sm text-muted">Opening your workspace…</div>
        </div>
      </div>
    );
  }

  return (
    <NavShell
      user={session.user}
      onLogout={() => {
        void signOut().then(() => router.replace("/login"));
      }}
    >
      {children}
    </NavShell>
  );
}
