"use client";

import { useState } from "react";

export function PolicyEditor({ policy }: { policy: any }) {
  const [form, setForm] = useState(policy);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
        <div className="section-title">Guardrails</div>
        <label className="mt-4 block">
          <div className="mb-2 text-sm text-slate">Allowed themes</div>
          <textarea
            value={form.allowed_themes.join(", ")}
            onChange={(event) => setForm({ ...form, allowed_themes: event.target.value.split(",").map((value: string) => value.trim()) })}
            className="min-h-32 w-full rounded-2xl border border-ink/10 p-4 outline-none"
          />
        </label>
        <label className="mt-4 block">
          <div className="mb-2 text-sm text-slate">Prohibited words</div>
          <textarea
            value={form.prohibited_words.join(", ")}
            onChange={(event) => setForm({ ...form, prohibited_words: event.target.value.split(",").map((value: string) => value.trim()) })}
            className="min-h-24 w-full rounded-2xl border border-ink/10 p-4 outline-none"
          />
        </label>
      </div>

      <div className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
        <div className="section-title">Scheduling + Approvals</div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block">
            <div className="mb-2 text-sm text-slate">Working hours start</div>
            <input
              type="number"
              value={form.working_hours_start}
              onChange={(event) => setForm({ ...form, working_hours_start: Number(event.target.value) })}
              className="w-full rounded-2xl border border-ink/10 px-4 py-3 outline-none"
            />
          </label>
          <label className="block">
            <div className="mb-2 text-sm text-slate">Working hours end</div>
            <input
              type="number"
              value={form.working_hours_end}
              onChange={(event) => setForm({ ...form, working_hours_end: Number(event.target.value) })}
              className="w-full rounded-2xl border border-ink/10 px-4 py-3 outline-none"
            />
          </label>
        </div>
        <div className="mt-6 flex items-center justify-between rounded-2xl bg-mist px-4 py-3">
          <div>
            <div className="font-semibold">Require second approval</div>
            <div className="text-sm text-slate">Two-person rule for campaign launch.</div>
          </div>
          <button
            type="button"
            onClick={() => setForm({ ...form, second_approval_required: !form.second_approval_required })}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${form.second_approval_required ? "bg-moss text-white" : "bg-white text-ink"}`}
          >
            {form.second_approval_required ? "Enabled" : "Disabled"}
          </button>
        </div>
      </div>
    </div>
  );
}
