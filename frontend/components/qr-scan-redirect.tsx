"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001/api/v1";

export function QrScanRedirect({ token }: { token: string }) {
  const router = useRouter();
  const [status, setStatus] = useState("Opening secure verification...");
  const scanRequest = useRef<Promise<void> | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (!scanRequest.current) {
      scanRequest.current = fetch(`${API_BASE}/public/training/${token}/events`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            event_type: "scanned_qr",
            metadata: {
              source: "qr_scan_route",
            },
          }),
        })
        .then(() => undefined)
        .catch(() => undefined);
    }

    void scanRequest.current.finally(() => {
        if (!cancelled) {
          setStatus("Loading verification page...");
          window.setTimeout(() => router.replace(`/training/${token}`), 500);
        }
    });

    return () => {
      cancelled = true;
    };
  }, [router, token]);

  return (
    <main className="page-shell flex min-h-screen items-center justify-center px-4 py-10">
      <section className="glass shell-ring max-w-xl rounded-[2rem] p-8 text-center shadow-card">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl border border-tide/30 bg-tide/15 text-3xl">
          QR
        </div>
        <div className="section-title mt-6">Secure QR Verification</div>
        <h1 className="mt-4 text-3xl font-semibold text-ink">{status}</h1>
        <p className="mt-3 text-sm leading-6 text-slate">
          Please wait while the request is verified.
        </p>
      </section>
    </main>
  );
}
