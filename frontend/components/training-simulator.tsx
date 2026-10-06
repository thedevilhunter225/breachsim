"use client";

import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE } from "@/lib/client-api";

type TrainingLanding = {
  landing_type?: string;
  campaign_name?: string | null;
  training_banner?: string;
  scenario?: {
    title?: string | null;
    channel?: string | null;
    theme?: string | null;
    subject?: string | null;
    body_copy?: string | null;
    cta_text?: string | null;
    landing_page_copy?: string | null;
    triggers?: string[];
  };
  preview_payload?: Record<string, unknown>;
};

async function sendTrainingEvent(token: string, eventType: string, metadata: Record<string, unknown> = {}) {
  const response = await fetch(`${API_BASE}/public/training/${token}/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      event_type: eventType,
      metadata,
    }),
  }).catch(() => null);
  return response?.ok ?? false;
}

function channelLabel(channel: string) {
  if (channel === "qr") return "QR";
  if (channel === "sms") return "SMS";
  if (channel === "vishing") return "Voice";
  return "Email";
}

function channelCopy(channel: string) {
  if (channel === "qr") {
    return {
      app: "Workplace Document Check",
      eyebrow: "QR verification",
      headline: "Confirm this workplace notice",
      intro: "This page opened from a QR notice. Verify the request before continuing.",
      requestType: "QR document verification",
      identifier: "QR scan source",
      primaryAction: "Open verification",
    };
  }

  if (channel === "sms") {
    return {
      app: "Northwind Secure Inbox",
      eyebrow: "Mobile verification",
      headline: "Action required from mobile alert",
      intro: "A workflow alert was opened from a mobile message. Confirm the source before taking action.",
      requestType: "SMS workflow alert",
      identifier: "Mobile notification",
      primaryAction: "Continue from alert",
    };
  }

  if (channel === "vishing") {
    return {
      app: "Northwind Call Desk",
      eyebrow: "Voice callback",
      headline: "Verify callback request",
      intro: "A phone-based request claims a workflow needs confirmation. Use known channels before sharing details.",
      requestType: "Voice verification request",
      identifier: "Callback reference",
      primaryAction: "Review callback",
    };
  }

  return {
    app: "Northwind WorkHub",
    eyebrow: "Secure workflow",
    headline: "Review assigned request",
    intro: "This workflow item was opened from a message. Confirm the source before taking action.",
    requestType: "Document approval",
    identifier: "Workflow reference",
    primaryAction: "Continue review",
  };
}

export function TrainingSimulator({ token, landing }: { token: string; landing: TrainingLanding }) {
  const [events, setEvents] = useState<string[]>([]);
  const [eventError, setEventError] = useState(false);
  const [reveal, setReveal] = useState<"none" | "cta" | "report" | "submit" | "verify">("none");
  const landingVisitRecorded = useRef(false);
  const deferredEvents = useDeferredValue(events);

  const channel = landing.scenario?.channel ?? landing.landing_type ?? "email";
  const copy = channelCopy(channel);
  const subject = landing.scenario?.subject ?? landing.scenario?.title ?? "Workflow review requested";
  const body = landing.scenario?.body_copy ?? "A workflow item has been assigned for review. Confirm the request before continuing.";
  const reference = `${channelLabel(channel)}-${token.slice(0, 8).toUpperCase()}`;
  const triggers = landing.scenario?.triggers?.length ? landing.scenario.triggers : ["urgency", "workflow trust"];

  const riskIndicators = useMemo(() => {
    const indicators = [
      "The request asks you to continue from a message instead of a known internal system.",
      "The page creates urgency around a routine workflow.",
      "The request uses familiar work context to lower suspicion.",
    ];
    if (channel === "qr") indicators[0] = "The QR notice does not prove who created or placed it.";
    if (channel === "sms") indicators[0] = "The mobile alert uses a short workflow path outside normal sign-in.";
    if (channel === "vishing") indicators[0] = "The caller identity cannot be trusted without an independent callback path.";
    return indicators;
  }, [channel]);

  useEffect(() => {
    if (landingVisitRecorded.current) return;
    landingVisitRecorded.current = true;
    void sendTrainingEvent(token, "visited_landing_page", { source: "landing_render", channel });
  }, [channel, token]);

  function addEvent(label: string, eventType: string, metadata: Record<string, unknown> = {}) {
    startTransition(() => {
      setEvents((current) => [`${new Date().toLocaleTimeString()}: ${label}`, ...current]);
    });
    setEventError(false);
    void sendTrainingEvent(token, eventType, metadata).then((recorded) => {
      if (!recorded) setEventError(true);
    });
  }

  function chooseToProvideDetails() {
    addEvent("Chose to provide account details", "submitted_form_boolean", {
      simulation_choice: "would_provide_details",
    });
    setReveal("submit");
  }

  function verifyIndependently() {
    addEvent("Chose to verify independently", "verified_out_of_band", {
      simulation_choice: "verify_independently",
    });
    setReveal("verify");
  }

  function continueReview() {
    addEvent("Clicked primary action", "clicked_link", { channel });
    setReveal("cta");
  }

  function reportSuspicious() {
    addEvent("Reported suspicious request", "clicked_report", { channel });
    setReveal("report");
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1.08fr_0.92fr]">
      <section className="overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
        <div className="border-b border-slate-200 bg-[#f8fafc] px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{copy.eyebrow}</div>
              <div className="mt-1 text-xl font-bold text-slate-950">{copy.app}</div>
            </div>
            <div className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-amber-700">
              Pending
            </div>
          </div>
        </div>

        <div className="grid gap-0 xl:grid-cols-[0.78fr_1.22fr]">
          <aside className="border-b border-slate-200 bg-slate-950 p-6 text-white xl:border-b-0 xl:border-r">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-200">{channelLabel(channel)} simulation</div>
            <h1 className="mt-4 text-3xl font-bold leading-tight">{copy.headline}</h1>
            <p className="mt-4 text-sm leading-7 text-slate-300">{copy.intro}</p>

            <div className="mt-6 rounded-2xl border border-white/10 bg-white/8 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-white/50">Message preview</div>
              <div className="mt-3 text-sm font-semibold text-white">{subject}</div>
              <p className="mt-3 text-sm leading-6 text-white/72">{body}</p>
            </div>
          </aside>

          <div className="p-6">
            <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-5">
              <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-950">{copy.requestType}</div>
                  <div className="mt-1 text-sm text-slate-500">{copy.identifier}: {reference}</div>
                </div>
                <div className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
                  Identity check
                </div>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2">
                <InfoTile label="Campaign" value={landing.campaign_name ?? "Awareness simulation"} />
                <InfoTile label="Theme" value={landing.scenario?.theme ?? "Workflow verification"} />
              </div>

              <div className="mt-5 space-y-4">
                <p className="text-sm leading-6 text-slate-600">
                  This request would lead to a step asking for account details. Choose how you would respond; no details are entered on this training page.
                </p>
                {reveal === "none" ? <div className="grid gap-3 md:grid-cols-2">
                  <button type="button" onClick={continueReview} className="rounded-xl bg-[#0f6c7d] px-4 py-3 text-sm font-semibold text-white">
                    {copy.primaryAction}
                  </button>
                  <button type="button" onClick={reportSuspicious} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-900">
                    Report suspicious
                  </button>
                  <button type="button" onClick={chooseToProvideDetails} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-900">
                    I would provide details
                  </button>
                  <button type="button" onClick={verifyIndependently} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-900">
                    Verify independently
                  </button>
                </div> : null}

                {eventError ? <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">Your choice could not be recorded. Check your connection before continuing.</div> : null}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-[1.5rem] border border-slate-200 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
        {reveal === "none" ? (
          <>
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Live simulation</div>
            <h2 className="mt-4 text-2xl font-bold text-slate-950">Choose how you would respond</h2>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The page intentionally looks like a normal workflow. Your action will reveal the training feedback.
            </p>
            <div className="mt-5 grid gap-3">
              {triggers.map((trigger) => (
                <div key={trigger} className="rounded-xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
                  Trigger: {trigger}
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-600">Security awareness result</div>
            <h2 className="mt-4 text-2xl font-bold text-slate-950">
              {reveal === "report" ? "Good response: you reported it" : reveal === "verify" ? "Good response: you verified independently" : "This was a phishing simulation"}
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              {reveal === "report" || reveal === "verify"
                ? "You chose a safer response. This training page records only the action you selected, never account details."
                : landing.training_banner ?? "No real credentials were stored. Only behavior events were recorded for training."}
            </p>
            <div className="mt-5 grid gap-3">
              {riskIndicators.map((indicator) => (
                <div key={indicator} className="rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">
                  {indicator}
                </div>
              ))}
            </div>
          </>
        )}

        <div className="mt-6 rounded-xl bg-slate-950 p-4 text-white">
          <div className="text-sm font-semibold">Event timeline</div>
          <div className="mt-3 space-y-2 text-sm text-white/70">
            {deferredEvents.length ? deferredEvents.map((event) => <div key={event}>{event}</div>) : <div>No events yet.</div>}
          </div>
        </div>
      </section>
    </div>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white p-4 text-sm">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-400">{label}</div>
      <div className="mt-2 font-semibold text-slate-950">{value}</div>
    </div>
  );
}
