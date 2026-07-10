"use client";

import { useEffect, useState } from "react";

import { Panel } from "@/components/panel";
import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import { approveScenario, editScenario, Employee, generateScenario, getEmployees, getScenarios, Scenario } from "@/lib/client-api";

const defaultForm = {
  employee_id: "",
  channel: "email",
  theme: "invoice/payment approval",
  difficulty_level: "medium",
  prompt_instructions: "Make it look like a normal internal workflow notification for this employee's role. Keep the initial message realistic and concise.",
};

function scenarioContentLabel(channel: string) {
  if (channel === "qr") return "QR Poster Title";
  if (channel === "sms") return "SMS Title";
  if (channel === "vishing") return "Vishing Script Title";
  return "Email Header";
}

function scenarioBodyLabel(channel: string) {
  if (channel === "qr") return "Poster Copy";
  if (channel === "sms") return "SMS Copy";
  if (channel === "vishing") return "Script Copy";
  return "Message Body";
}

function aiProviderLabel(metadata?: Record<string, unknown>) {
  const provider = typeof metadata?.provider === "string" ? metadata.provider : "rule-based";
  const model = typeof metadata?.model === "string" ? metadata.model : "fallback";
  if (provider === "ollama") return `Ollama local · ${model}`;
  if (provider === "openai") return `OpenAI · ${model}`;
  if (provider === "gemini") return `Gemini AI · ${model}`;
  return "AI fallback engine · scenario generator";
}

function metadataList(value: unknown) {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

export function ScenarioLabConsole() {
  const { session } = useSession();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [form, setForm] = useState(defaultForm);
  const [message, setMessage] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [editingScenarioId, setEditingScenarioId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    subject: "",
    body_copy: "",
    cta_text: "",
    landing_page_copy: "",
    notes: "",
  });

  async function loadData() {
    if (!session) return;
    const [employeeRows, scenarioRows] = await Promise.all([
      getEmployees(session.access_token),
      getScenarios(session.access_token),
    ]);
    setEmployees(employeeRows);
    setScenarios(scenarioRows);
    if (!form.employee_id && employeeRows[0]) {
      setForm((current) => ({ ...current, employee_id: employeeRows[0].id }));
    }
  }

  useEffect(() => {
    void loadData();
  }, [session]);

  async function handleGenerate() {
    if (!session) return;
    setIsGenerating(true);
    setMessage("Generating with local Ollama. This can take 30-90 seconds on CPU.");
    try {
      await generateScenario(session.access_token, form);
      setMessage("Scenario generated.");
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Scenario generation failed.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleApprove(scenarioId: string) {
    if (!session) return;
    await approveScenario(session.access_token, scenarioId);
    setMessage("Scenario approved.");
    await loadData();
  }

  function startEditingScenario(scenario: Scenario) {
    if (!scenario.latest_version) return;
    setEditingScenarioId(scenario.id);
    setEditForm({
      subject: scenario.latest_version.subject,
      body_copy: scenario.latest_version.body_copy,
      cta_text: scenario.latest_version.cta_text,
      landing_page_copy: scenario.latest_version.landing_page_copy,
      notes: scenario.latest_version.notes ?? "",
    });
    setMessage(`Editing ${scenario.title}. Save changes to create a new scenario version.`);
  }

  function cancelEditingScenario() {
    setEditingScenarioId(null);
    setEditForm({
      subject: "",
      body_copy: "",
      cta_text: "",
      landing_page_copy: "",
      notes: "",
    });
    setMessage("Scenario edit cancelled.");
  }

  async function saveScenarioEdit(scenarioId: string) {
    if (!session) return;
    await editScenario(session.access_token, scenarioId, editForm);
    setEditingScenarioId(null);
    setMessage("Scenario updated. Re-approve this version before sending.");
    await loadData();
  }

  return (
    <>
      <Panel className="bg-white/90 text-ink">
        <div className="section-title">Scenario Lab</div>
        <h2 className="mt-4 text-3xl font-semibold text-ink">Generate and approve phishing scenarios from the admin UI</h2>
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <div className="rounded-[1.1rem] border border-ink/10 bg-sand/70 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate">1. Context</div>
            <div className="mt-2 text-sm font-semibold text-ink">Employee role and department</div>
          </div>
          <div className="rounded-[1.1rem] border border-ink/10 bg-sand/70 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate">2. AI Generate</div>
            <div className="mt-2 text-sm font-semibold text-ink">Message, CTA, landing copy</div>
          </div>
          <div className="rounded-[1.1rem] border border-ink/10 bg-sand/70 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate">3. Scope Check</div>
            <div className="mt-2 text-sm font-semibold text-ink">Domain and launch validation</div>
          </div>
          <div className="rounded-[1.1rem] border border-ink/10 bg-sand/70 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate">4. Human Review</div>
            <div className="mt-2 text-sm font-semibold text-ink">Edit, version, approve</div>
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel className="bg-white/90 text-ink">
          <div className="section-title">Generate Scenario</div>
          <div className="mt-4 rounded-[1.25rem] border border-tide/15 bg-tide/10 p-4 text-sm leading-6 text-ink">
            This sends the selected employee context, channel, theme, and difficulty to the AI scenario engine. The generated content is checked against policy before it becomes a draft.
          </div>
          <div className="mt-4 grid gap-4">
            <select value={form.employee_id} onChange={(event) => setForm({ ...form, employee_id: event.target.value })} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none">
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>{employee.full_name} · {employee.department_name}</option>
              ))}
            </select>
            <select value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none">
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="qr">QR</option>
              <option value="vishing">Vishing Script</option>
            </select>
            <select value={form.theme} onChange={(event) => setForm({ ...form, theme: event.target.value })} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none">
              <option value="invoice/payment approval">Invoice/payment approval</option>
              <option value="password reset">Password reset</option>
              <option value="policy update">Policy update</option>
              <option value="client contract">Client contract</option>
              <option value="qr verification">QR verification</option>
            </select>
            <select value={form.difficulty_level} onChange={(event) => setForm({ ...form, difficulty_level: event.target.value })} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
            <label className="grid gap-2">
              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate">AI Prompt</span>
              <textarea
                value={form.prompt_instructions}
                onChange={(event) => setForm({ ...form, prompt_instructions: event.target.value })}
                placeholder="Tell the AI what kind of scenario to generate for this employee context."
                className="min-h-32 rounded-2xl border border-ink/10 bg-white px-4 py-3 text-sm leading-6 outline-none"
              />
            </label>
            {message ? <div className="rounded-2xl bg-moss/10 px-4 py-3 text-sm text-moss">{message}</div> : null}
            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="rounded-2xl bg-ink px-4 py-3 font-semibold text-mist disabled:cursor-wait disabled:opacity-60"
            >
              {isGenerating ? "Generating..." : "Generate Scenario"}
            </button>
          </div>
        </Panel>

        <Panel className="bg-white/90 text-ink">
          <div className="section-title">Versioned Drafts</div>
          <div className="mt-5 grid gap-4">
            {scenarios.map((scenario) => (
              <div key={scenario.id} className="rounded-[1.5rem] border border-ink/10 bg-white p-5 shadow-sm">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h3 className="text-xl font-semibold text-ink">{scenario.title}</h3>
                    <div className="mt-2 text-sm text-slate">
                      {scenario.channel.toUpperCase()} · {scenario.theme} · difficulty {scenario.difficulty_level}
                    </div>
                  </div>
                  <StatusBadge value={scenario.status} />
                </div>
                <div className="mt-4 text-sm leading-7 text-slate">{scenario.latest_version?.body_copy}</div>
                {scenario.latest_version ? (
                  <div className="mt-4 grid gap-3 rounded-[1.25rem] border border-ink/10 bg-sand/70 p-4 text-sm">
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate">{scenarioContentLabel(scenario.channel)}</div>
                      <div className="mt-1 font-semibold text-ink">{scenario.latest_version.subject}</div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate">CTA</div>
                      <div className="mt-1 font-semibold text-ink">{scenario.latest_version.cta_text}</div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate">Landing Copy</div>
                      <div className="mt-1 text-slate">{scenario.latest_version.landing_page_copy}</div>
                    </div>
                    <div className="grid gap-3 border-t border-ink/10 pt-4 md:grid-cols-3">
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-slate">AI Engine</div>
                        <div className="mt-1 font-semibold text-ink">{aiProviderLabel(scenario.latest_version.rationale_metadata)}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-slate">Difficulty Score</div>
                        <div className="mt-1 font-semibold text-ink">{scenario.latest_version.difficulty_score}/100</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-slate">Policy Check</div>
                        <div className="mt-1 font-semibold text-ink">{scenario.latest_version.validation_result?.passed ? "Passed" : "Needs review"}</div>
                      </div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate">AI Inputs Used</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate">theme: {String(scenario.latest_version.rationale_metadata?.theme ?? scenario.theme)}</span>
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate">channel: {String(scenario.latest_version.rationale_metadata?.channel ?? scenario.channel)}</span>
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate">difficulty: {String(scenario.latest_version.rationale_metadata?.difficulty_level ?? scenario.difficulty_level)}</span>
                        {scenario.latest_version.rationale_metadata?.prompt_instructions ? (
                          <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate">prompt: custom</span>
                        ) : null}
                        {metadataList(scenario.latest_version.rationale_metadata?.previous_failure_reasons).map((reason) => (
                          <span key={reason} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate">past signal: {reason}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  {scenario.detected_persuasion_triggers.map((trigger) => (
                    <span key={trigger} className="rounded-full bg-tide/10 px-3 py-1 text-xs font-semibold text-tide">
                      {trigger}
                    </span>
                  ))}
                </div>
                {editingScenarioId === scenario.id ? (
                  <div className="mt-5 grid gap-3">
                    <input value={editForm.subject} onChange={(event) => setEditForm({ ...editForm, subject: event.target.value })} placeholder="Subject" className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                    <textarea value={editForm.body_copy} onChange={(event) => setEditForm({ ...editForm, body_copy: event.target.value })} placeholder={scenarioBodyLabel(scenario.channel)} className="min-h-40 rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                    <input value={editForm.cta_text} onChange={(event) => setEditForm({ ...editForm, cta_text: event.target.value })} placeholder="CTA text" className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                    <textarea value={editForm.landing_page_copy} onChange={(event) => setEditForm({ ...editForm, landing_page_copy: event.target.value })} placeholder="Landing page copy" className="min-h-28 rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                    <textarea value={editForm.notes} onChange={(event) => setEditForm({ ...editForm, notes: event.target.value })} placeholder="Editor notes" className="min-h-24 rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                    <div className="flex flex-wrap gap-3">
                      <button onClick={() => void saveScenarioEdit(scenario.id)} className="rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-mist">
                        Save New Version
                      </button>
                      <button onClick={cancelEditingScenario} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 text-sm font-semibold text-ink">
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-5 flex flex-wrap gap-3">
                    <button onClick={() => startEditingScenario(scenario)} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 text-sm font-semibold text-ink">
                      Edit Message
                    </button>
                    {scenario.status !== "approved" ? (
                      <button onClick={() => handleApprove(scenario.id)} className="rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-mist">
                        Approve Scenario
                      </button>
                    ) : null}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}
