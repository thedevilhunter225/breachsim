"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Panel } from "@/components/panel";
import {
  ApiError,
  type EmployeePortalSummary,
  getPortalSummary,
  portalCompleteTraining,
  portalOptOut,
  portalRequestRedaction,
} from "@/lib/client-api";

const TOKEN_STORAGE_KEY = "breachsim.portal_link";

const CONSENT_COPY: Record<EmployeePortalSummary["consent_status"], string> = {
  consented: "Included in your organization's awareness programme",
  pending: "Awaiting your organization's consent record",
  opted_out: "Opted out — you will not receive further simulations",
  redaction_requested: "Deletion requested — your organization's administrators can see this request",
};

const TREND_COPY: Record<EmployeePortalSummary["trend"], { label: string; tone: string }> = {
  improving: { label: "Improving", tone: "text-moss" },
  stable: { label: "Steady", tone: "text-ink" },
  worsening: { label: "Needs attention", tone: "text-breach" },
};

/** Reads the exercise link from the URL fragment once, then keeps it out of the address bar. */
function readPortalLink(): string | null {
  const fragment = new URLSearchParams(window.location.hash.slice(1)).get("t");
  try {
    if (fragment) {
      window.sessionStorage.setItem(TOKEN_STORAGE_KEY, fragment);
    }
    const stored = fragment ?? window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
    if (fragment) window.history.replaceState(null, "", window.location.pathname);
    return stored;
  } catch {
    return fragment;
  }
}

export function EmployeePortal() {
  const [token, setToken] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [summary, setSummary] = useState<EmployeePortalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const openedAt = useRef<Record<string, number>>({});

  useEffect(() => {
    const link = readPortalLink();
    setToken(link);
    setChecked(true);
    if (!link) return;
    getPortalSummary(link)
      .then(setSummary)
      .catch((reason: unknown) => {
        const expired = reason instanceof ApiError && (reason.status === 404 || reason.status === 410);
        setError(
          expired
            ? "This link has expired or is no longer valid. Open the portal from the link at the end of your most recent exercise."
            : "Your portal could not be loaded. Check your connection and try again.",
        );
      });
  }, []);

  async function run(action: string, operation: () => Promise<EmployeePortalSummary>, success: string) {
    setBusy(action);
    setError(null);
    setNotice(null);
    try {
      setSummary(await operation());
      setNotice(success);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The request could not be completed.");
    } finally {
      setBusy(null);
    }
  }

  function confirmThen(message: string, action: () => void) {
    if (window.confirm(message)) action();
  }

  const withdrawn = summary?.consent_status === "opted_out" || summary?.consent_status === "redaction_requested";

  return (
    <main className="page-shell min-h-screen px-4 py-6 md:px-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <Panel>
          <div className="section-title">Employee portal</div>
          <h1 className="mt-4 text-3xl font-semibold text-ink md:text-4xl">
            {summary ? `Hi ${summary.first_name}` : "Your awareness history and privacy choices"}
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate">
            See the training assigned to you, how your awareness is developing, and what information your
            organization uses for these exercises. You can opt out or ask for your exercise data to be deleted.
          </p>
        </Panel>

        {notice ? (
          <div role="status" className="rounded-2xl bg-moss/10 px-4 py-3 text-sm text-moss">
            {notice}
          </div>
        ) : null}
        {error ? (
          <div role="alert" className="rounded-2xl bg-breach/8 px-4 py-3 text-sm text-breach">
            {error}
          </div>
        ) : null}

        {checked && !token ? (
          <Panel>
            <div className="section-title">How to open your portal</div>
            <p className="mt-4 text-sm leading-7 text-slate">
              Your portal opens from the link at the end of any awareness exercise you take part in. That link
              identifies you without a password. If you no longer have it, ask your security or IT team.
            </p>
          </Panel>
        ) : null}

        {token && !summary && !error ? (
          <Panel>
            <p className="text-sm text-slate">Loading your portal…</p>
          </Panel>
        ) : null}

        {summary ? (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <Panel>
                <div className="section-title">Your progress</div>
                <div className={`mt-4 text-2xl font-semibold ${TREND_COPY[summary.trend].tone}`}>
                  {TREND_COPY[summary.trend].label}
                </div>
                <p className="mt-2 text-sm leading-6 text-slate">
                  Based on how your responses in exercises have changed over time.
                </p>
              </Panel>
              <Panel>
                <div className="section-title">Participation</div>
                <div className="mt-4 text-sm font-semibold text-ink">{CONSENT_COPY[summary.consent_status]}</div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="app-secondary-button"
                    disabled={withdrawn || busy !== null}
                    onClick={() =>
                      confirmThen("Opt out of future awareness simulations?", () =>
                        void run("opt-out", () => portalOptOut(token!), "You have opted out of future simulations."),
                      )
                    }
                  >
                    Opt out of simulations
                  </button>
                  <button
                    type="button"
                    className="app-secondary-button"
                    disabled={summary.consent_status === "redaction_requested" || busy !== null}
                    onClick={() =>
                      confirmThen(
                        "Ask your organization to delete your exercise data? You will also stop receiving simulations.",
                        () =>
                          void run(
                            "redaction",
                            () => portalRequestRedaction(token!),
                            "Your deletion request was recorded. Your organization's administrators see it in their directory.",
                          ),
                      )
                    }
                  >
                    Request deletion of my data
                  </button>
                </div>
              </Panel>
            </div>

            <Panel>
              <div className="section-title">Your training</div>
              {summary.training.length === 0 ? (
                <p className="mt-4 text-sm text-slate">No training has been assigned to you.</p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {summary.training.map((item) => {
                    const completed = item.status === "completed";
                    return (
                      <li key={item.id} className="rounded-xl border border-line p-4">
                        <details
                          onToggle={(event) => {
                            if ((event.currentTarget as HTMLDetailsElement).open && !openedAt.current[item.id]) {
                              openedAt.current[item.id] = Date.now();
                            }
                          }}
                        >
                          <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2">
                            <span className="font-semibold text-ink">{item.title}</span>
                            <span className={completed ? "text-xs font-semibold text-moss" : "text-xs font-semibold text-slate"}>
                              {completed ? "Completed" : "To do"}
                            </span>
                          </summary>
                          <p className="mt-3 text-sm leading-7 text-slate">{item.body}</p>
                          {item.guidance_points.length ? (
                            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-slate">
                              {item.guidance_points.map((point) => (
                                <li key={point}>{point}</li>
                              ))}
                            </ul>
                          ) : null}
                          {!completed ? (
                            <button
                              type="button"
                              className="app-primary-button mt-4"
                              disabled={busy !== null}
                              onClick={() =>
                                void run(
                                  `training-${item.id}`,
                                  () =>
                                    portalCompleteTraining(
                                      token!,
                                      item.id,
                                      (Date.now() - (openedAt.current[item.id] ?? Date.now())) / 1000,
                                    ),
                                  "Training marked as complete.",
                                )
                              }
                            >
                              Mark as complete
                            </button>
                          ) : null}
                        </details>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Panel>

            <Panel>
              <div className="section-title">What information is used</div>
              <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-7 text-slate">
                <li>Your name, work email, department and role, as provided by your organization.</li>
                <li>Context your organization approved for realistic exercises.</li>
                <li>The choices you make in exercises and the training you complete.</li>
                <li>Passwords, verification codes and payment details are never collected.</li>
              </ul>
              {summary.privacy_notice ? (
                <p className="mt-4 whitespace-pre-line text-sm leading-7 text-slate">{summary.privacy_notice}</p>
              ) : null}
            </Panel>
          </>
        ) : null}

        <p className="text-xs text-slate">
          <Link href="/legal/privacy" className="underline underline-offset-2">
            Privacy notice
          </Link>
          {" · "}
          <Link href="/legal/employee-notice" className="underline underline-offset-2">
            About this programme
          </Link>
        </p>
      </div>
    </main>
  );
}
