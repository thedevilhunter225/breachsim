"use client";

import { useState } from "react";

const initialPreview = {
  subject: "Invoice/payment approval: review requested",
  body_copy:
    "Hi Amina,\n\nA finance workflow item is waiting in your approval queue. Please review the summary before the next approval batch closes.\n\nRequest owner: Finance Operations\nAssigned queue: Analyst\nReference: FIN-INPA-32\n\nUse the link below to open the workflow item and confirm whether it should move forward.",
  cta_text: "clickhere",
  landing_page_copy: "Training simulation only. No real credentials are stored."
};

export function ScenarioGeneratorForm() {
  const [preview, setPreview] = useState(initialPreview);
  const [theme, setTheme] = useState("invoice/payment approval");
  const [channel, setChannel] = useState("email");

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="rounded-md border border-ink/10 bg-white/80 p-4">
        <div className="section-title">Generate</div>
        <div className="mt-4 space-y-4 text-sm">
          <label className="block">
            <div className="mb-2 text-slate">Theme</div>
            <select value={theme} onChange={(event) => setTheme(event.target.value)} className="w-full rounded-md border border-ink/10 bg-white px-4 py-3 outline-none">
              <option>invoice/payment approval</option>
              <option>password reset</option>
              <option>policy update</option>
              <option>client contract</option>
            </select>
          </label>
          <label className="block">
            <div className="mb-2 text-slate">Channel</div>
            <select value={channel} onChange={(event) => setChannel(event.target.value)} className="w-full rounded-md border border-ink/10 bg-white px-4 py-3 outline-none">
              <option>email</option>
              <option>qr</option>
              <option>sms</option>
              <option>vishing</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() =>
              setPreview((current) => ({
                ...current,
                subject: `${theme}: review requested`,
                body_copy:
                  channel === "qr"
                    ? `Scan to open the current ${theme} request for the Operations queue.\n\nReference: OPS-${theme.slice(0, 4).toUpperCase()}-32\nAuthorized access: employees only`
                    : `Hi Amina,\n\nA ${theme} item is waiting in the Operations workflow queue. Please review the summary before the next workflow update closes.\n\nRequest owner: Operations\nAssigned queue: Analyst\nReference: OPS-${theme.slice(0, 4).toUpperCase()}-32\n\nUse the link below to open the workflow item and confirm whether it should move forward.`,
                cta_text: channel === "qr" ? "Scan to open" : "clickhere",
              }))
            }
            className="w-full rounded-md bg-ink px-4 py-3 font-semibold text-mist"
          >
            Generate Preview
          </button>
        </div>
      </div>

      <div className="rounded-md border border-ink/10 bg-white/80 p-5">
        <div className="section-title">Admin Review Preview</div>
        <h3 className="mt-4 text-2xl font-semibold">{preview.subject}</h3>
        <p className="mt-4 whitespace-pre-line text-sm leading-7 text-slate">{preview.body_copy}</p>
        <div className="mt-6 rounded-md bg-tide/10 px-4 py-3 text-sm text-tide">{preview.cta_text}</div>
        <div className="mt-6 rounded-md border border-dashed border-ink/20 bg-mist px-4 py-4 text-sm text-slate">
          Landing copy: {preview.landing_page_copy}
        </div>
      </div>
    </div>
  );
}
