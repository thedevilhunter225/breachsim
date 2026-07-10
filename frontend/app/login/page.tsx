"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useSession } from "@/components/session-provider";
import { BrandLogo } from "@/components/brand-logo";

const platformSignals = [
  "Open employee portal",
  "Live Delivery",
  "Audit Trail",
  "Adaptive Training",
];

const leftRailPoints = [
  "Configure company directory and approved employee context",
  "Generate realistic phishing simulations with review before launch",
  "Track clicks, reports, form submits, and risk movement over time",
];

export default function LoginPage() {
  const router = useRouter();
  const { ready, session, signIn } = useSession();
  const [email, setEmail] = useState("admin@breachsim-lab.com");
  const [password, setPassword] = useState("Admin123!");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (ready && session) {
      router.replace("/dashboard");
    }
  }, [ready, router, session]);

  async function handleLogin() {
    setSubmitting(true);
    setError(null);
    try {
      await signIn(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText("admin@breachsim-lab.com / Admin123!");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#07111c] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(68,227,255,0.18),transparent_24%),radial-gradient(circle_at_bottom_left,rgba(58,182,214,0.12),transparent_28%),radial-gradient(circle_at_top_right,rgba(89,112,171,0.14),transparent_26%),linear-gradient(180deg,#08111d_0%,#091321_50%,#050b14_100%)]" />
      <div className="absolute inset-0 opacity-40 [background-image:radial-gradient(circle_at_18%_22%,rgba(255,255,255,0.6)_0,rgba(255,255,255,0)_1.4px),radial-gradient(circle_at_74%_18%,rgba(255,255,255,0.45)_0,rgba(255,255,255,0)_1.1px),radial-gradient(circle_at_36%_82%,rgba(255,255,255,0.38)_0,rgba(255,255,255,0)_1.1px),radial-gradient(circle_at_88%_76%,rgba(255,255,255,0.32)_0,rgba(255,255,255,0)_1px)]" />
      <div className="pointer-events-none absolute -left-24 top-10 h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(82,229,255,0.18),rgba(82,229,255,0)_66%)] blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 top-0 opacity-55">
        <svg viewBox="0 0 1440 960" className="h-full w-full" preserveAspectRatio="none" aria-hidden="true">
          <path d="M-40 740C122 654 283 614 448 620c173 7 317 71 464 54 157-18 308-115 568-87" stroke="rgba(132,232,255,0.12)" strokeWidth="2" fill="none" />
          <path d="M-60 556C112 473 282 451 452 462c174 12 323 101 488 91 148-10 284-99 560-62" stroke="rgba(169,242,255,0.16)" strokeWidth="2" fill="none" />
          <path d="M30 334c144 27 259 79 417 73 172-6 307-74 471-57 173 19 305 89 548 62" stroke="rgba(146,224,255,0.12)" strokeWidth="2" fill="none" />
        </svg>
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-[1360px] items-center px-4 py-6 sm:px-6 lg:px-8">
        <div className="grid w-full overflow-hidden rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(11,16,29,0.96),rgba(8,14,25,0.94))] shadow-[0_30px_120px_rgba(0,0,0,0.45)] xl:grid-cols-[0.9fr_1.1fr]">
          <section className="relative min-h-[560px] overflow-hidden border-b border-white/8 px-8 py-8 sm:px-10 xl:border-b-0 xl:border-r xl:border-white/8 xl:px-12 xl:py-10">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_22%_34%,rgba(94,230,255,0.2),transparent_28%),radial-gradient(circle_at_48%_55%,rgba(147,227,255,0.14),transparent_26%),linear-gradient(180deg,rgba(18,65,92,0.34),rgba(8,18,35,0.08))]" />
            <div className="absolute inset-y-0 right-0 w-px bg-white/8" />
            <div className="absolute inset-x-0 bottom-0 h-48 bg-[linear-gradient(180deg,rgba(6,13,24,0),rgba(6,13,24,0.78))]" />
            <div className="pointer-events-none absolute inset-0 opacity-70">
              <svg viewBox="0 0 620 820" className="h-full w-full" preserveAspectRatio="none" aria-hidden="true">
                <path d="M-24 604C143 454 321 392 559 410" stroke="rgba(159,240,255,0.22)" strokeWidth="2" fill="none" />
                <path d="M-58 690C150 505 337 450 636 484" stroke="rgba(132,232,255,0.18)" strokeWidth="2" fill="none" />
                <path d="M-20 760C188 571 390 541 658 577" stroke="rgba(189,244,255,0.16)" strokeWidth="2" fill="none" />
              </svg>
            </div>

            <div className="relative flex h-full flex-col">
              <BrandLogo inverted />

              <div className="mt-12 max-w-sm">
                <div className="rounded-full border border-white/12 bg-white/6 px-4 py-2 text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-cyan-100/70">
                  Control Center
                </div>
                <h1 className="display-font mt-6 text-4xl font-semibold tracking-[-0.05em] text-white sm:text-[3.2rem]">
                  Human risk operations for live phishing simulations.
                </h1>
                <p className="mt-5 max-w-md text-sm leading-7 text-white/68">
                  Configure the company directory, generate believable scenarios, review campaigns, and monitor human risk behavior without leaving the admin console.
                </p>
              </div>

              <div className="mt-auto space-y-4 pt-10">
                {leftRailPoints.map((point, index) => (
                  <div key={point} className="flex items-start gap-4 rounded-[1.2rem] border border-white/10 bg-white/6 px-4 py-4 backdrop-blur-sm">
                    <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full border border-cyan-300/20 bg-cyan-300/10 text-xs font-semibold text-cyan-100">
                      0{index + 1}
                    </div>
                    <div className="text-sm leading-6 text-white/78">{point}</div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="relative px-8 py-8 sm:px-10 xl:px-12 xl:py-12">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(71,99,188,0.12),transparent_26%),radial-gradient(circle_at_bottom_left,rgba(69,225,255,0.08),transparent_24%)]" />
            <div className="relative mx-auto max-w-[38rem]">
              <div className="section-title !text-white/48">Admin Sign In</div>
              <h2 className="display-font mt-4 text-4xl font-semibold tracking-[-0.05em] text-white sm:text-[3rem]">
                Sign in to the control center
              </h2>
              <p className="mt-4 max-w-2xl text-base leading-8 text-white/62">
                Sign in as the company security admin to configure the directory, generate scenarios, review campaigns, and inspect risk intelligence.
              </p>

              <form
                className="mt-10 space-y-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  void handleLogin();
                }}
              >
                <label className="block">
                  <div className="mb-3 text-xs uppercase tracking-[0.28em] text-white/42">Email</div>
                  <input
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="h-14 w-full rounded-[1.35rem] border border-white/10 bg-white/[0.035] px-5 text-lg text-white outline-none placeholder:text-white/28"
                  />
                </label>

                <label className="block">
                  <div className="mb-3 text-xs uppercase tracking-[0.28em] text-white/42">Password</div>
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="h-14 w-full rounded-[1.35rem] border border-white/20 bg-white px-5 text-lg font-medium text-slate-950 outline-none placeholder:text-slate-400"
                  />
                </label>

                {error ? <div className="rounded-[1.2rem] border border-[#ff9b7b]/25 bg-[#ff8d6a]/12 px-4 py-3 text-sm text-[#ffd8ca]">{error}</div> : null}

                <button
                  type="submit"
                  disabled={submitting}
                  className="h-14 w-full rounded-[1.35rem] border border-cyan-200/14 bg-[linear-gradient(180deg,#3a8ea3_0%,#2a778b_35%,#1c5968_100%)] text-lg font-semibold text-white shadow-[0_16px_32px_rgba(42,119,139,0.28)] disabled:opacity-60"
                >
                  {submitting ? "Entering BreachSim..." : "Enter BreachSim"}
                </button>
              </form>

              <div className="mt-10 rounded-[1.5rem] border border-white/10 bg-white/[0.035] px-5 py-5 backdrop-blur-sm">
                <div className="text-xs uppercase tracking-[0.28em] text-white/40">Demo Credentials</div>
                <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-lg font-medium tracking-[-0.02em] text-white/84">admin@breachsim-lab.com / Admin123!</div>
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/[0.02] px-4 py-2 text-sm font-medium text-white/78 shadow-none"
                  >
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
              </div>

              <div className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-3 text-sm text-white/56">
                <Link href="/employee-portal" className="font-medium text-cyan-100/88">
                  Open employee portal
                </Link>
                {platformSignals.slice(1).map((signal) => (
                  <div key={signal} className="flex items-center gap-4">
                    <span className="hidden h-1 w-1 rounded-full bg-white/24 sm:block" />
                    <span>{signal}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
