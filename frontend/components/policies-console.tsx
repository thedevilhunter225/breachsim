"use client";

import { useEffect, useState } from "react";

import { Panel } from "@/components/panel";
import { useSession } from "@/components/session-provider";
import { getPolicy, Policy, updatePolicy } from "@/lib/client-api";

export function PoliciesConsole() {
  const { session } = useSession();
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    void getPolicy(session.access_token).then(setPolicy);
  }, [session]);

  async function savePolicy() {
    if (!session || !policy) return;
    const next = await updatePolicy(session.access_token, {
      ...policy,
      id: undefined,
      organization_id: undefined,
    });
    setPolicy(next);
    setMessage("Policy updated.");
  }

  if (!policy) {
    return <Panel>Loading policy...</Panel>;
  }

  return (
    <>
      <Panel>
        <div className="section-title">Simulation Scope</div>
        <h2 className="mt-2 text-2xl font-semibold">Control realism without weakening the training flow</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate">
          These settings define which realistic business scenarios the AI can create, which channels can be used, and how often employees can be tested.
        </p>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <div className="section-title">Realism Scope</div>
          <div className="mt-4 grid gap-4">
            <label className="block">
              <div className="text-sm font-semibold text-ink">Scenario themes AI can generate</div>
              <div className="mt-1 text-xs leading-5 text-slate">Use realistic workplace themes such as invoices, password resets, QR notices, contracts, and policy updates.</div>
              <textarea value={policy.allowed_themes.join(", ")} onChange={(event) => setPolicy({ ...policy, allowed_themes: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} className="mt-2 min-h-24 w-full rounded-md border border-ink/10 p-3 outline-none" />
            </label>
            <label className="block">
              <div className="text-sm font-semibold text-ink">Never-use topics</div>
              <div className="mt-1 text-xs leading-5 text-slate">Keep only topics that would create legal, HR, medical, or physical-safety risk for employees.</div>
              <textarea value={policy.prohibited_words.join(", ")} onChange={(event) => setPolicy({ ...policy, prohibited_words: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} className="mt-2 min-h-24 w-full rounded-md border border-ink/10 p-3 outline-none" />
            </label>
            <label className="block">
              <div className="text-sm font-semibold text-ink">Training domains</div>
              <div className="mt-1 text-xs leading-5 text-slate">Where simulation landing pages and tracked training links are hosted.</div>
              <textarea value={policy.approved_training_domains.join(", ")} onChange={(event) => setPolicy({ ...policy, approved_training_domains: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} className="mt-2 min-h-20 w-full rounded-md border border-ink/10 p-3 outline-none" />
            </label>
          </div>
        </Panel>
        <Panel>
          <div className="section-title">Launch Controls</div>
          <div className="mt-4 grid gap-4">
            <label className="block">
              <div className="text-sm font-semibold text-ink">Earliest send hour</div>
              <div className="mt-1 text-xs leading-5 text-slate">Campaigns should not launch before this hour.</div>
              <input type="number" value={policy.working_hours_start} onChange={(event) => setPolicy({ ...policy, working_hours_start: Number(event.target.value) })} className="mt-2 w-full rounded-md border border-ink/10 px-3 py-2.5 outline-none" />
            </label>
            <label className="block">
              <div className="text-sm font-semibold text-ink">Latest send hour</div>
              <div className="mt-1 text-xs leading-5 text-slate">Campaigns should not launch after this hour.</div>
              <input type="number" value={policy.working_hours_end} onChange={(event) => setPolicy({ ...policy, working_hours_end: Number(event.target.value) })} className="mt-2 w-full rounded-md border border-ink/10 px-3 py-2.5 outline-none" />
            </label>
            <label className="block">
              <div className="text-sm font-semibold text-ink">Max campaigns per employee</div>
              <div className="mt-1 text-xs leading-5 text-slate">Limits how often one employee can be targeted in the policy window.</div>
              <input type="number" value={policy.maximum_frequency_per_employee} onChange={(event) => setPolicy({ ...policy, maximum_frequency_per_employee: Number(event.target.value) })} className="mt-2 w-full rounded-md border border-ink/10 px-3 py-2.5 outline-none" />
            </label>
            <label className="flex items-center gap-3 text-sm text-slate">
              <input type="checkbox" checked={policy.second_approval_required} onChange={(event) => setPolicy({ ...policy, second_approval_required: event.target.checked })} />
              Require second approval before launch
            </label>
            {message ? <div className="rounded-md border border-moss/20 bg-moss/10 px-3 py-2.5 text-sm text-moss">{message}</div> : null}
            <button onClick={savePolicy} className="rounded-md bg-ink px-4 py-2.5 font-semibold text-mist">Save Policy</button>
          </div>
        </Panel>
      </div>
    </>
  );
}
