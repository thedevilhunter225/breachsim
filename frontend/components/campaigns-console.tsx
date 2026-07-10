"use client";

import { useEffect, useState } from "react";

import { Panel } from "@/components/panel";
import { QrPosterPreview } from "@/components/qr-poster-preview";
import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import {
  Campaign,
  createCampaign,
  deliverCampaignEmail,
  DeliveryAttempt,
  Employee,
  getCampaigns,
  getDeliveryAttempts,
  getEmployees,
  getScenarios,
  launchCampaignSandbox,
  requestCampaignApproval,
  approveCampaign,
  Scenario,
} from "@/lib/client-api";

export function CampaignsConsole() {
  const { session } = useSession();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedEmployees, setSelectedEmployees] = useState<string[]>([]);
  const [form, setForm] = useState({
    name: "",
    description: "",
    channel: "email",
    scenario_id: "",
    requires_second_approval: false,
    sandbox_mode: true,
    learning_objective: "Recognize phishing patterns.",
  });
  const [message, setMessage] = useState<string | null>(null);

  async function loadData() {
    if (!session) return;
    const [campaignRows, attemptRows, employeeRows, scenarioRows] = await Promise.all([
      getCampaigns(session.access_token),
      getDeliveryAttempts(session.access_token),
      getEmployees(session.access_token),
      getScenarios(session.access_token),
    ]);
    const approvedScenarios = scenarioRows.filter((scenario) => scenario.status === "approved");
    setCampaigns(campaignRows);
    setAttempts(attemptRows);
    setEmployees(employeeRows);
    setScenarios(approvedScenarios);
    setForm((current) => {
      if (current.scenario_id) {
        return current;
      }
      const matchingScenario = approvedScenarios.find((scenario) => scenario.channel === current.channel) ?? approvedScenarios[0];
      return { ...current, scenario_id: matchingScenario?.id ?? "" };
    });
  }

  useEffect(() => {
    void loadData();
  }, [session]);

  async function handleCreate() {
    if (!session || !selectedEmployees.length || !form.scenario_id) return;
    await createCampaign(session.access_token, {
      name: form.name,
      description: form.description,
      channel: form.channel,
      campaign_type: "one_time",
      throttling_per_hour: 25,
      target_employee_ids: selectedEmployees,
      scenario_ids: [form.scenario_id],
      requires_second_approval: form.requires_second_approval,
      sandbox_mode: form.sandbox_mode,
      learning_objective: form.learning_objective,
      target_filters: { created_from_ui: true },
    });
    setMessage("Campaign created.");
    setForm({
      name: "",
      description: "",
      channel: "email",
      scenario_id: scenarios[0]?.id ?? "",
      requires_second_approval: false,
      sandbox_mode: true,
      learning_objective: "Recognize phishing patterns.",
    });
    setSelectedEmployees([]);
    await loadData();
  }

  async function runAction(action: () => Promise<unknown>, success: string) {
    await action();
    setMessage(success);
    await loadData();
  }

  const channelScenarios = scenarios.filter((scenario) => scenario.channel === form.channel);
  const selectableScenarios = channelScenarios.length ? channelScenarios : scenarios;

  function updateChannel(channel: string) {
    const nextScenario = scenarios.find((scenario) => scenario.channel === channel)?.id ?? scenarios[0]?.id ?? "";
    setForm({ ...form, channel, scenario_id: nextScenario });
  }

  function copyValue(value?: string) {
    if (!value) return;
    void navigator.clipboard?.writeText(value);
    setMessage("Copied to clipboard.");
  }

  return (
    <>
      <Panel>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="section-title">Campaign Operations</div>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Simulation campaign console</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate">
              Build a campaign, approve it, deliver through the selected channel, then track behavior and risk movement.
            </p>
          </div>
          <div className="grid w-full grid-cols-3 gap-2 text-center text-xs font-semibold uppercase tracking-[0.12em] text-slate lg:w-auto">
            <div className="rounded-md border border-ink/10 bg-slate-50 px-4 py-2">Draft</div>
            <div className="rounded-md border border-ink/10 bg-slate-50 px-4 py-2">Approve</div>
            <div className="rounded-md bg-ink px-4 py-2 text-white">Deliver</div>
          </div>
        </div>
      </Panel>

      <Panel>
        <div className="section-title">Campaign Modules</div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <ModuleTile title="Groups" value={`${employees.length} targets`} detail="Directory employees" />
          <ModuleTile title="Templates" value={`${scenarios.length} approved`} detail="Scenario drafts" />
          <ModuleTile title="Landing Pages" value="Tracked" detail="Training pages" />
          <ModuleTile title="Sending Profile" value="Sandbox/live" detail="Delivery config" />
          <ModuleTile title="Campaigns" value={`${campaigns.length} total`} detail="Launch objects" />
          <ModuleTile title="Results" value={`${attempts.length} events`} detail="Attempts timeline" />
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel>
          <div className="section-title">Create Campaign</div>
          <div className="mt-4 grid gap-4">
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Campaign name" className="rounded-md border border-ink/10 px-3 py-2.5 outline-none" />
            <textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Description" className="min-h-20 rounded-md border border-ink/10 px-3 py-2.5 outline-none" />
            <select value={form.channel} onChange={(event) => updateChannel(event.target.value)} className="rounded-md border border-ink/10 px-3 py-2.5 outline-none">
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="qr">QR</option>
              <option value="vishing">Vishing Script</option>
            </select>
            <select value={form.scenario_id} onChange={(event) => setForm({ ...form, scenario_id: event.target.value })} className="rounded-md border border-ink/10 px-3 py-2.5 outline-none">
              {selectableScenarios.map((scenario) => (
                <option key={scenario.id} value={scenario.id}>{scenario.title}</option>
              ))}
            </select>
            <div className="enterprise-muted-card rounded-lg p-4">
              <div className="text-sm font-semibold text-ink">Target Employees</div>
              <div className="mt-3 grid gap-2">
                {employees.slice(0, 12).map((employee) => {
                  const checked = selectedEmployees.includes(employee.id);
                  return (
                    <label key={employee.id} className="flex items-center gap-3 text-sm text-slate">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          setSelectedEmployees((current) =>
                            event.target.checked ? [...current, employee.id] : current.filter((id) => id !== employee.id)
                          );
                        }}
                      />
                      <span>{employee.full_name} - {employee.email}</span>
                    </label>
                  );
                })}
              </div>
            </div>
            <label className="flex items-center gap-3 text-sm text-slate">
              <input type="checkbox" checked={form.requires_second_approval} onChange={(event) => setForm({ ...form, requires_second_approval: event.target.checked })} />
              Require second approval
            </label>
            <input value={form.learning_objective} onChange={(event) => setForm({ ...form, learning_objective: event.target.value })} placeholder="Learning objective" className="rounded-md border border-ink/10 px-3 py-2.5 outline-none" />
            {message ? <div className="rounded-md border border-moss/20 bg-moss/10 px-3 py-2.5 text-sm text-moss">{message}</div> : null}
            <button onClick={handleCreate} className="rounded-md bg-ink px-4 py-2.5 font-semibold text-white">Create Campaign</button>
          </div>
        </Panel>

        <Panel>
          <div className="section-title">Campaign Actions</div>
          <div className="mt-5 space-y-3">
            {campaigns.map((campaign) => {
              const latestAttempt = attempts.find((attempt) => attempt.campaign_id === campaign.id);
              const isQrAttempt = Boolean(latestAttempt?.preview_payload.qr_image_data_url);

              return (
                <div key={campaign.id} className="enterprise-card rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xl font-semibold text-ink">{campaign.name}</h3>
                    <StatusBadge value={campaign.status} />
                  </div>
                  <p className="mt-3 text-sm text-slate">{campaign.description}</p>
                  <div className="mt-4 grid grid-cols-3 gap-3 border-y border-ink/10 py-3 text-sm">
                    <div>
                      <div className="font-semibold text-ink">{campaign.channel.toUpperCase()}</div>
                      <div className="text-slate">Channel</div>
                    </div>
                    <div>
                      <div className="font-semibold text-ink">{campaign.target_count}</div>
                      <div className="text-slate">Targets</div>
                    </div>
                    <div>
                      <div className="font-semibold text-ink">{campaign.scenario_count}</div>
                      <div className="text-slate">Variants</div>
                    </div>
                  </div>
                  {latestAttempt ? (
                    <div className="mt-5 grid gap-3 rounded-lg border border-ink/10 bg-slate-50 p-4 text-sm">
                      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate">{isQrAttempt ? "QR Campaign Asset" : "Email Delivery Details"}</div>
                      {isQrAttempt ? (
                        <QrPosterPreview payload={latestAttempt.preview_payload} />
                      ) : (
                        <>
                          <div><span className="font-semibold text-ink">From:</span> {latestAttempt.preview_payload.sender_name ? `${latestAttempt.preview_payload.sender_name} <${latestAttempt.preview_payload.from_email ?? "configured sender"}>` : latestAttempt.preview_payload.from_email ?? "Configured sender"}</div>
                          <div><span className="font-semibold text-ink">To:</span> {latestAttempt.preview_payload.recipient ?? "Preview only"}</div>
                          <div><span className="font-semibold text-ink">Subject:</span> {latestAttempt.preview_payload.subject}</div>
                          <div><span className="font-semibold text-ink">CTA:</span> {latestAttempt.preview_payload.cta_text}</div>
                          <div className="rounded-md border border-ink/10 bg-white px-3 py-2.5 text-slate">{latestAttempt.preview_payload.body_copy}</div>
                        </>
                      )}
                    </div>
                  ) : null}
                  <div className="mt-5 flex flex-wrap gap-3">
                    {campaign.status === "draft" ? (
                      <button onClick={() => void runAction(() => requestCampaignApproval(session!.access_token, campaign.id), "Approval requested.")} className="rounded-md bg-ink px-4 py-2.5 text-sm font-semibold text-white">
                        Request Approval
                      </button>
                    ) : null}
                    {campaign.status === "pending_approval" ? (
                      <button onClick={() => void runAction(() => approveCampaign(session!.access_token, campaign.id), "Campaign approved.")} className="rounded-md bg-moss px-4 py-2.5 text-sm font-semibold text-white">
                        Approve
                      </button>
                    ) : null}
                    {(campaign.status === "approved" || campaign.status === "scheduled") ? (
                      <button onClick={() => void runAction(() => launchCampaignSandbox(session!.access_token, campaign.id), "Campaign asset generated.")} className="rounded-md bg-tide px-4 py-2.5 text-sm font-semibold text-white">
                        {campaign.channel === "qr" ? "Generate QR Asset" : campaign.channel === "sms" ? "Create SMS Asset" : "Create Tracking Link"}
                      </button>
                    ) : null}
                    {isQrAttempt ? (
                      <>
                        <button onClick={() => copyValue(latestAttempt?.preview_payload.scan_url)} className="rounded-md border border-ink/10 bg-white px-4 py-2.5 text-sm font-semibold text-ink">
                          Copy QR Link
                        </button>
                        <a href={latestAttempt?.preview_payload.qr_image_data_url} download="breachsim-qr.png" className="rounded-md border border-ink/10 bg-white px-4 py-2.5 text-sm font-semibold text-ink">
                          Download QR
                        </a>
                      </>
                    ) : null}
                    {(campaign.status === "approved" || campaign.status === "scheduled" || campaign.status === "active") && campaign.channel === "email" ? (
                      <button onClick={() => void runAction(() => deliverCampaignEmail(session!.access_token, campaign.id), "Live emails sent.")} className="rounded-md bg-ember px-4 py-2.5 text-sm font-semibold text-white">
                        Send Live Email
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>

      <Panel>
        <div className="section-title">Delivery Attempts</div>
        <div className="mt-5 space-y-3">
          {attempts.map((attempt) => (
            <div key={attempt.id} className="enterprise-card rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="font-semibold">{attempt.preview_payload.subject}</div>
                <StatusBadge value={attempt.status} />
              </div>
              {attempt.preview_payload.qr_image_data_url ? (
                <div className="mt-4">
                  <QrPosterPreview payload={attempt.preview_payload} compact />
                </div>
              ) : (
                <>
                  <div className="mt-3 text-sm text-slate">From: {attempt.preview_payload.sender_name ? `${attempt.preview_payload.sender_name} <${attempt.preview_payload.from_email ?? "configured sender"}>` : attempt.preview_payload.from_email ?? "Configured sender"}</div>
                  <div className="mt-3 text-sm text-slate">Recipient: {attempt.preview_payload.recipient ?? "preview only"}</div>
                  <div className="mt-1 text-sm text-slate">Preview URL: <span className="font-semibold text-ink">{attempt.preview_payload.preview_url}</span></div>
                </>
              )}
              <div className="mt-3 rounded-md border border-ink/10 bg-white px-3 py-2.5 text-sm leading-6 text-slate">{attempt.preview_payload.body_copy}</div>
              {attempt.preview_payload.error ? <div className="mt-3 rounded-md bg-ember/10 px-3 py-2.5 text-sm text-ember">{attempt.preview_payload.error}</div> : null}
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}

function ModuleTile({ title, value, detail }: { title: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-ink/10 bg-slate-50 p-4">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate">{title}</div>
      <div className="mt-2 text-lg font-semibold text-ink">{value}</div>
      <div className="mt-1 text-xs text-slate">{detail}</div>
    </div>
  );
}
