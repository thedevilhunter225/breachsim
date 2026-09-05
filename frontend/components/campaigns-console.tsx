"use client";

import clsx from "clsx";
import {
  Activity,
  CheckCircle2,
  Copy,
  ExternalLink,
  Loader2,
  Mail,
  MessageSquare,
  PhoneCall,
  QrCode,
  Rocket,
  Send,
  ShieldCheck,
  Target,
  Trash2,
  Video,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { QrPosterPreview } from "@/components/qr-poster-preview";
import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import {
  approveCampaign,
  createCampaign,
  createCampaignRun,
  deleteCampaign,
  getCampaigns,
  getDeliveryAttempts,
  getCampaignRuns,
  getEnterpriseEmailConnections,
  getEmployees,
  getOrganizationDomains,
  getScenarios,
  launchCampaignSandbox,
  requestCampaignApproval,
  type Campaign,
  type CampaignRun,
  type DeliveryAttempt,
  type Employee,
  type Scenario,
  type EnterpriseEmailConnection,
  type OrganizationDomain,
} from "@/lib/client-api";

const CHANNELS: Array<{ value: string; label: string; icon: LucideIcon; deliverLabel: string }> = [
  { value: "email", label: "Email", icon: Mail, deliverLabel: "Send live email" },
  { value: "sms", label: "SMS", icon: MessageSquare, deliverLabel: "Send live SMS" },
  { value: "qr", label: "QR", icon: QrCode, deliverLabel: "Send QR email" },
  { value: "vishing", label: "Voice", icon: PhoneCall, deliverLabel: "Activate call session" },
  { value: "deepfake", label: "Deepfake", icon: Video, deliverLabel: "Activate media session" },
];

function channelMeta(channel: string) {
  return CHANNELS.find((entry) => entry.value === channel) ?? CHANNELS[0];
}

function readError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const raw = String((error as Error).message);
    try {
      const parsed = JSON.parse(raw);
      return typeof parsed === "string" ? parsed : raw;
    } catch {
      return raw;
    }
  }
  return "Action failed.";
}

export function CampaignsConsole() {
  const { session } = useSession();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [domains, setDomains] = useState<OrganizationDomain[]>([]);
  const [connections, setConnections] = useState<EnterpriseEmailConnection[]>([]);
  const [runs, setRuns] = useState<CampaignRun[]>([]);
  const [selectedEmployees, setSelectedEmployees] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    channel: "email",
    scenario_id: "",
    requires_second_approval: true,
    sandbox_mode: true,
    learning_objective: "Recognize social engineering patterns.",
    landing_domain_id: "",
    email_connection_id: "",
  });

  const loadData = useCallback(async () => {
    if (!session) return;
    const [campaignRows, attemptRows, employeeRows, scenarioRows, domainRows, connectionRows] = await Promise.all([
      getCampaigns(session.access_token),
      getDeliveryAttempts(session.access_token),
      getEmployees(session.access_token),
      getScenarios(session.access_token),
      getOrganizationDomains(session.access_token),
      getEnterpriseEmailConnections(session.access_token),
    ]);
    const runRows = (
      await Promise.all(campaignRows.map((campaign) => getCampaignRuns(session.access_token, campaign.id).catch(() => [])))
    ).flat();
    const approved = scenarioRows.filter((scenario) => scenario.status === "approved");
    setCampaigns(campaignRows);
    setAttempts(attemptRows);
    setEmployees(employeeRows);
    setScenarios(approved);
    setDomains(domainRows);
    setConnections(connectionRows);
    setRuns(runRows);
    setForm((current) => {
      if (current.scenario_id) return current;
      const match = approved.find((scenario) => scenario.channel === current.channel) ?? approved[0];
      return {
        ...current,
        scenario_id: match?.id ?? "",
        landing_domain_id: current.landing_domain_id || domainRows.find((row) => row.purpose === "landing" && row.status === "active" && row.is_primary)?.id || domainRows.find((row) => row.purpose === "landing" && row.status === "active")?.id || "",
        email_connection_id: current.email_connection_id || connectionRows.find((row) => row.status === "healthy")?.id || "",
      };
    });
  }, [session]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const channelScenarios = useMemo(
    () => scenarios.filter((scenario) => scenario.channel === form.channel),
    [scenarios, form.channel],
  );

  function updateChannel(channel: string) {
    const next = scenarios.find((scenario) => scenario.channel === channel)?.id ?? "";
    setForm({ ...form, channel, scenario_id: next, sandbox_mode: channel === "email" || channel === "qr" ? form.sandbox_mode : true });
  }

  async function runAction(key: string, action: () => Promise<unknown>, success: string) {
    setBusy(key);
    setNotice(null);
    try {
      await action();
      setNotice({ tone: "ok", text: success });
      await loadData();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusy(null);
    }
  }

  async function handleCreate() {
    if (!session || !selectedEmployees.length || !form.scenario_id) return;
    await runAction(
      "create",
      () =>
        createCampaign(session.access_token, {
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
          landing_domain_id: form.landing_domain_id || null,
          email_connection_id: form.email_connection_id || null,
        }),
      "Campaign created.",
    );
    setForm((current) => ({ ...current, name: "", description: "" }));
    setSelectedEmployees([]);
  }

  async function handleDelete(campaign: Campaign) {
    if (!session) return;
    if (!window.confirm(`Delete campaign "${campaign.name}"? This cannot be undone.`)) return;

    setBusy(campaign.id);
    setNotice(null);
    try {
      const result = await deleteCampaign(session.access_token, campaign.id);
      setNotice({ tone: "ok", text: `Deleted "${result.label}".` });
      await loadData();
    } catch (error) {
      const message = readError(error);
      // The API refuses to erase recorded evidence unless the caller opts in explicitly.
      if (message.toLowerCase().includes("purge_evidence")) {
        const confirmedPurge = window.confirm(
          `"${campaign.name}" holds recorded simulation evidence.\n\n` +
            `Deleting it destroys the proof that this exercise ran, including employee ` +
            `interactions and training assignments.\n\nPurge the evidence and delete anyway?`,
        );
        if (confirmedPurge) {
          try {
            const result = await deleteCampaign(session.access_token, campaign.id, true);
            const events = result.removed?.events ?? 0;
            setNotice({
              tone: "ok",
              text: `Deleted "${result.label}" and purged ${events} recorded event(s). The purge is in the audit trail.`,
            });
            await loadData();
          } catch (purgeError) {
            setNotice({ tone: "error", text: readError(purgeError) });
          }
        }
      } else {
        setNotice({ tone: "error", text: message });
      }
    } finally {
      setBusy(null);
    }
  }

  function copyValue(value?: string) {
    if (!value) return;
    void navigator.clipboard?.writeText(value);
    setNotice({ tone: "ok", text: "Copied to clipboard." });
  }

  const liveReady = Boolean(form.landing_domain_id && form.email_connection_id);
  const canCreate = Boolean(
    form.name.trim() &&
      form.scenario_id &&
      selectedEmployees.length &&
      (form.sandbox_mode || ((form.channel === "email" || form.channel === "qr") && liveReady)),
  );

  return (
    <div className="space-y-4">
      <section className="card p-5 md:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="section-title">Campaign operations</div>
            <h1 className="display-font mt-1.5 text-2xl font-bold text-ink">Campaign control</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
              Create, dual-approve and deliver simulations across email, SMS, QR, voice and synthetic media.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2.5">
            <Stat icon={Target} label="Directory" value={employees.length} />
            <Stat icon={CheckCircle2} label="Approved" value={scenarios.length} tone="text-signal" />
            <Stat icon={Activity} label="Campaigns" value={campaigns.length} />
          </div>
        </div>
      </section>

      {notice ? (
        <div
          className={clsx(
            "rounded-xl border px-4 py-3 text-[0.85rem]",
            notice.tone === "ok"
              ? "border-signal/25 bg-signal/8 text-signal"
              : "border-breach/25 bg-breach/8 text-breach",
          )}
        >
          {notice.text}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[400px_minmax(0,1fr)]">
        {/* Composer */}
        <section className="card min-w-0 self-start overflow-hidden p-5">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
              <Send size={18} />
            </div>
            <div>
              <div className="section-title">Composer</div>
              <h2 className="display-font mt-0.5 text-lg font-bold text-ink">Create campaign</h2>
            </div>

            <div className="rounded-xl border border-line bg-surface-muted p-4">
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={!form.sandbox_mode}
                  disabled={form.channel !== "email" && form.channel !== "qr"}
                  onChange={(event) => setForm({ ...form, sandbox_mode: !event.target.checked })}
                />
                <span>
                  <span className="block text-sm font-semibold text-ink">Live enterprise delivery</span>
                  <span className="mt-1 block text-xs leading-5 text-muted">
                    Available only for approved Email and QR campaigns. Other channels remain sandbox-only.
                  </span>
                </span>
              </label>
              {!form.sandbox_mode ? (
                <div className="mt-4 grid gap-3">
                  <div>
                    <label className="field-label" htmlFor="campaign-landing-domain">Landing domain</label>
                    <select id="campaign-landing-domain" className="field" value={form.landing_domain_id} onChange={(event) => setForm({ ...form, landing_domain_id: event.target.value })}>
                      <option value="">Select verified landing domain</option>
                      {domains.filter((row) => row.purpose === "landing" && row.status === "active").map((row) => <option key={row.id} value={row.id}>{row.hostname}{row.is_primary ? " · primary" : ""}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="field-label" htmlFor="campaign-email-connection">Authorized sender</label>
                    <select id="campaign-email-connection" className="field" value={form.email_connection_id} onChange={(event) => setForm({ ...form, email_connection_id: event.target.value })}>
                      <option value="">Select healthy email connection</option>
                      {connections.filter((row) => row.status === "healthy").map((row) => <option key={row.id} value={row.id}>{row.sender_name} · {row.sender_email}</option>)}
                    </select>
                  </div>
                  {!liveReady ? <p className="text-xs leading-5 text-caution">Complete domain and customer mail authorization in Settings → Launch setup.</p> : null}
                </div>
              ) : null}
            </div>
          </div>

          <div className="mt-5 grid gap-4">
            <div>
              <label className="field-label" htmlFor="campaign-name">
                Campaign name
              </label>
              <input
                id="campaign-name"
                className="field"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                placeholder="Q3 Finance Awareness Drill"
              />
            </div>

            <div>
              <label className="field-label" htmlFor="campaign-description">
                Description
              </label>
              <textarea
                id="campaign-description"
                className="field min-h-20"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                placeholder="What this campaign is testing and why."
              />
            </div>

            <div>
              <span className="field-label">Channel</span>
              <div className="grid grid-cols-5 gap-1.5">
                {CHANNELS.map((channel) => {
                  const Icon = channel.icon;
                  const active = form.channel === channel.value;
                  const available = scenarios.some((scenario) => scenario.channel === channel.value);
                  return (
                    <button
                      key={channel.value}
                      type="button"
                      onClick={() => updateChannel(channel.value)}
                      className={clsx(
                        "flex flex-col items-center gap-1.5 rounded-lg border px-1 py-2.5 transition",
                        active
                          ? "border-brand-500 bg-brand-500/10 text-brand-600"
                          : "border-line bg-surface text-muted hover:border-line-strong hover:text-ink",
                        !available && !active && "opacity-45",
                      )}
                      title={available ? channel.label : `No approved ${channel.label} scenario yet`}
                    >
                      <Icon size={16} />
                      <span className="text-[0.62rem] font-bold">{channel.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="field-label" htmlFor="campaign-scenario">
                Approved scenario
              </label>
              <select
                id="campaign-scenario"
                className="field"
                value={form.scenario_id}
                onChange={(event) => setForm({ ...form, scenario_id: event.target.value })}
                disabled={channelScenarios.length === 0}
              >
                {channelScenarios.length === 0 ? (
                  <option value="">No approved {channelMeta(form.channel).label} scenario</option>
                ) : (
                  channelScenarios.map((scenario) => (
                    <option key={scenario.id} value={scenario.id}>
                      {scenario.title}
                    </option>
                  ))
                )}
              </select>
              {channelScenarios.length === 0 ? (
                <p className="field-hint">
                  Generate and approve a {channelMeta(form.channel).label} scenario in Scenario Studio first.
                </p>
              ) : null}
            </div>

            <div>
              <div className="flex items-center justify-between">
                <span className="field-label !mb-0">Target employees</span>
                <span className="text-[0.72rem] font-semibold text-muted">{selectedEmployees.length} selected</span>
              </div>
              <div className="mt-2 max-h-56 space-y-1 overflow-y-auto rounded-xl border border-line bg-surface-muted p-2">
                {employees.map((employee) => {
                  const checked = selectedEmployees.includes(employee.id);
                  return (
                    <label
                      key={employee.id}
                      className={clsx(
                        "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-[0.8rem] transition",
                        checked ? "bg-brand-500/10 text-ink" : "text-muted hover:bg-surface",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) =>
                          setSelectedEmployees((current) =>
                            event.target.checked
                              ? [...current, employee.id]
                              : current.filter((id) => id !== employee.id),
                          )
                        }
                      />
                      <span className="min-w-0 flex-1 truncate">
                        <span className="font-semibold">{employee.full_name}</span>
                        <span className="ml-1.5 text-subtle">{employee.email}</span>
                      </span>
                      <span className="numeric shrink-0 text-[0.7rem] font-bold text-subtle">
                        {employee.risk_score}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>

            <label className="flex cursor-pointer items-center gap-2.5 text-[0.82rem] text-muted">
              <input
                type="checkbox"
                checked={form.requires_second_approval}
                onChange={(event) => setForm({ ...form, requires_second_approval: event.target.checked })}
              />
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck size={14} className="text-brand-500" />
                Require a second administrator approval
              </span>
            </label>

            <div>
              <label className="field-label" htmlFor="campaign-objective">
                Learning objective
              </label>
              <input
                id="campaign-objective"
                className="field"
                value={form.learning_objective}
                onChange={(event) => setForm({ ...form, learning_objective: event.target.value })}
              />
            </div>

            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={!canCreate || busy === "create"}
              className="btn-primary w-full"
            >
              {busy === "create" ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              Create campaign
            </button>
          </div>
        </section>

        {/* Workflow */}
        <section className="min-w-0 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="section-title">Launch queue</div>
              <h2 className="display-font mt-0.5 text-xl font-bold text-ink">Campaign workflow</h2>
            </div>
            <span className="badge badge-neutral">{campaigns.length} total</span>
          </div>

          {campaigns.length === 0 ? (
            <div className="card px-5 py-16 text-center">
              <Rocket className="mx-auto text-subtle" size={30} />
              <p className="mt-3 text-[0.92rem] font-semibold text-ink">No campaigns yet</p>
              <p className="mx-auto mt-1.5 max-w-sm text-[0.83rem] leading-relaxed text-muted">
                Create one from the composer once you have an approved scenario.
              </p>
            </div>
          ) : (
            campaigns.map((campaign) => {
              const meta = channelMeta(campaign.channel);
              const ChannelIcon = meta.icon;
              const attempt = attempts.find((row) => row.campaign_id === campaign.id);
              const latestRun = runs.filter((row) => row.campaign_id === campaign.id).sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
              const launchable = campaign.status === "approved" || campaign.status === "scheduled";
              const deliverable = !campaign.sandbox_mode && (campaign.channel === "email" || campaign.channel === "qr") && launchable;

              return (
                <article key={campaign.id} className="card overflow-hidden">
                  <div className="flex flex-col gap-3 border-b border-line p-5 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="badge badge-brand">
                          <ChannelIcon size={11} />
                          {meta.label}
                        </span>
                        <StatusBadge value={campaign.status} />
                        {campaign.requires_second_approval ? (
                          <span className="badge badge-neutral">
                            <ShieldCheck size={11} />
                            Dual approval
                          </span>
                        ) : null}
                      </div>
                      <h3 className="display-font mt-2.5 text-lg font-bold text-ink">{campaign.name}</h3>
                      {campaign.description ? (
                        <p className="mt-1 text-[0.83rem] leading-relaxed text-muted">{campaign.description}</p>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 gap-4 text-center">
                      <div>
                        <div className="numeric display-font text-lg font-bold text-ink">{campaign.target_count}</div>
                        <div className="text-[0.62rem] font-bold uppercase tracking-wide text-subtle">Targets</div>
                      </div>
                      <div>
                        <div className="numeric display-font text-lg font-bold text-ink">{campaign.scenario_count}</div>
                        <div className="text-[0.62rem] font-bold uppercase tracking-wide text-subtle">Variants</div>
                      </div>
                    </div>
                  </div>

                  {attempt ? (
                    <div className="border-b border-line bg-surface-muted p-5">
                      <AttemptPreview attempt={attempt} onCopy={copyValue} />
                    </div>
                  ) : null}

                  {latestRun ? (
                    <div className="grid gap-px border-b border-line bg-line sm:grid-cols-4 lg:grid-cols-8">
                      <RunMetric label="State" value={latestRun.status} />
                      <RunMetric label="Queued" value={latestRun.queued_count} />
                      <RunMetric label="Processing" value={latestRun.processing_count} />
                      <RunMetric label="Accepted" value={latestRun.accepted_count} tone="text-signal" />
                      <RunMetric label="Bounced" value={latestRun.bounced_count} />
                      <RunMetric label="Suppressed" value={latestRun.suppressed_count} />
                      <RunMetric label="Failed" value={latestRun.failed_count} tone="text-breach" />
                      <RunMetric label="Unknown" value={latestRun.unknown_count} tone="text-caution" />
                    </div>
                  ) : null}

                  <div className="flex flex-wrap gap-2.5 p-5">
                    {campaign.status === "draft" ? (
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        disabled={busy === campaign.id}
                        onClick={() =>
                          void runAction(
                            campaign.id,
                            () => requestCampaignApproval(session!.access_token, campaign.id),
                            "Approval requested.",
                          )
                        }
                      >
                        Request approval
                      </button>
                    ) : null}

                    {campaign.status === "pending_approval" ? (
                      <button
                        type="button"
                        className="btn-primary btn-sm"
                        disabled={busy === campaign.id}
                        onClick={() =>
                          void runAction(
                            campaign.id,
                            () => approveCampaign(session!.access_token, campaign.id),
                            "Approval recorded. A second admin may still be required.",
                          )
                        }
                      >
                        <CheckCircle2 size={13} />
                        Approve
                      </button>
                    ) : null}

                    {launchable ? (
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        disabled={busy === campaign.id}
                        onClick={() =>
                          void runAction(
                            campaign.id,
                            () => launchCampaignSandbox(session!.access_token, campaign.id),
                            "Sandbox assets generated. Nothing was sent.",
                          )
                        }
                      >
                        Preview in sandbox
                      </button>
                    ) : null}

                    {deliverable ? (
                      <button
                        type="button"
                        className="btn-primary btn-sm"
                        disabled={busy === campaign.id}
                        onClick={() =>
                          void runAction(
                            campaign.id,
                            () => createCampaignRun(session!.access_token, campaign.id, campaign.schedule_at),
                            `${meta.label} campaign queued for provider submission.`,
                          )
                        }
                      >
                        {busy === campaign.id ? (
                          <Loader2 size={13} className="animate-spin" />
                        ) : (
                          <Rocket size={13} />
                        )}
                        {meta.deliverLabel}
                      </button>
                    ) : null}

                    <button
                      type="button"
                      className="btn-danger btn-sm ml-auto"
                      disabled={busy === campaign.id}
                      onClick={() => void handleDelete(campaign)}
                      title="Delete this campaign"
                    >
                      {busy === campaign.id ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <Trash2 size={13} />
                      )}
                      Delete
                    </button>
                  </div>
                </article>
              );
            })
          )}
        </section>
      </div>

      {/* Delivery ledger */}
      <section className="card overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <h2 className="display-font text-lg font-bold text-ink">Delivery attempts</h2>
          <span className="badge badge-neutral">{attempts.length} recorded</span>
        </div>
        {attempts.length === 0 ? (
          <p className="px-5 py-12 text-center text-[0.85rem] text-muted">
            No delivery attempts yet. Launch a campaign to populate the ledger.
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {attempts.map((attempt) => {
              const meta = channelMeta(attempt.channel);
              const ChannelIcon = meta.icon;
              return (
                <li key={attempt.id} className="p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="badge badge-brand">
                      <ChannelIcon size={11} />
                      {meta.label}
                    </span>
                    <StatusBadge value={attempt.status} />
                    {attempt.sandbox_mode ? <span className="badge badge-neutral">Sandbox</span> : null}
                    <span className="ml-auto text-[0.74rem] text-subtle">
                      {attempt.delivered_at ? new Date(attempt.delivered_at).toLocaleString() : "Not delivered"}
                    </span>
                  </div>
                  <div className="mt-2.5 text-[0.9rem] font-semibold text-ink">
                    {attempt.preview_payload.subject ?? "Simulation asset"}
                  </div>
                  <div className="mt-3">
                    <AttemptPreview attempt={attempt} onCopy={copyValue} compact />
                  </div>
                  {attempt.preview_payload.sandbox_reason ? (
                    <p className="mt-3 rounded-lg border border-caution/25 bg-caution/8 px-3 py-2 text-[0.8rem] leading-relaxed text-caution">
                      {attempt.preview_payload.sandbox_reason}
                    </p>
                  ) : null}
                  {attempt.preview_payload.error ? (
                    <p className="mt-3 rounded-lg border border-breach/20 bg-breach/8 px-3 py-2 text-[0.8rem] text-breach">
                      {attempt.preview_payload.error}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

/* ------------------------------------------------- channel-aware previews */

function AttemptPreview({
  attempt,
  onCopy,
  compact = false,
}: {
  attempt: DeliveryAttempt;
  onCopy: (value?: string) => void;
  compact?: boolean;
}) {
  const payload = attempt.preview_payload ?? {};

  if (attempt.channel === "qr") {
    return <QrPosterPreview payload={payload} compact={compact} />;
  }

  if (attempt.channel === "vishing") {
    return (
      <div className="space-y-2.5">
        <div className="grid gap-2.5 sm:grid-cols-2">
          <Row label="Caller ID" value={payload.caller_id_display} mono />
          <Row label="Presents as" value={payload.spoofed_display_name} />
          <Row label="Call reason" value={payload.call_reason} />
          <Row label="Decision points" value={payload.script_step_count} />
        </div>
        <LinkRow label="Call session" url={payload.call_url} onCopy={onCopy} />
        {payload.delivery_note ? <Note text={payload.delivery_note} /> : null}
      </div>
    );
  }

  if (attempt.channel === "deepfake") {
    return (
      <div className="space-y-2.5">
        <div className="grid gap-2.5 sm:grid-cols-2">
          <Row label="Impersonates" value={payload.sender_display_name} />
          <Row label="Modality" value={String(payload.modality ?? "").replace(/_/g, " ")} />
          <Row label="Requested action" value={payload.requested_action} />
          <Row label="Synthetic tells" value={payload.artifact_count} />
        </div>
        <LinkRow label="Media session" url={payload.media_url} onCopy={onCopy} />
        {payload.delivery_note ? <Note text={payload.delivery_note} /> : null}
      </div>
    );
  }

  if (attempt.channel === "sms") {
    return (
      <div className="space-y-2.5">
        <div className="grid gap-2.5 sm:grid-cols-2">
          <Row label="Recipient" value={payload.recipient ?? "Preview only"} mono />
          <Row
            label="Length"
            value={
              payload.character_count
                ? `${payload.character_count} chars · ${payload.encoding ?? "GSM-7"} · ${payload.segment_count} segment(s)`
                : "—"
            }
          />
        </div>
        {payload.message_text ? (
          <p className="rounded-lg border border-line bg-surface p-3 text-[0.83rem] leading-relaxed text-ink">
            {payload.message_text}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      <div className="grid gap-2.5 sm:grid-cols-2">
        <Row
          label="From"
          value={
            payload.sender_name
              ? `${payload.sender_name} <${payload.from_email ?? "configured sender"}>`
              : (payload.from_email ?? "Configured sender")
          }
        />
        <Row label="To" value={payload.recipient ?? "Preview only"} mono />
        <Row label="Subject" value={payload.subject} />
        <Row label="CTA" value={payload.cta_text} />
      </div>
      {payload.body_copy ? (
        <p className="whitespace-pre-line rounded-lg border border-line bg-surface p-3 text-[0.83rem] leading-relaxed text-ink">
          {payload.body_copy}
        </p>
      ) : null}
      <LinkRow label="Tracking link" url={payload.preview_url} onCopy={onCopy} />
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value?: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className={clsx("mt-0.5 text-[0.83rem] font-medium text-ink", mono && "numeric font-mono text-[0.79rem]")}>
        {value ?? "—"}
      </div>
    </div>
  );
}

function LinkRow({
  label,
  url,
  onCopy,
}: {
  label: string;
  url?: string;
  onCopy: (value?: string) => void;
}) {
  if (!url) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2">
      <span className="eyebrow">{label}</span>
      <span className="numeric min-w-0 flex-1 truncate font-mono text-[0.76rem] text-muted">{url}</span>
      <button type="button" className="btn-ghost btn-sm" onClick={() => onCopy(url)}>
        <Copy size={12} />
        Copy
      </button>
      <a href={url} target="_blank" rel="noreferrer" className="btn-ghost btn-sm">
        <ExternalLink size={12} />
        Open
      </a>
    </div>
  );
}

function Note({ text }: { text: string }) {
  return (
    <p className="rounded-lg border border-brand-500/20 bg-brand-500/6 px-3 py-2 text-[0.78rem] leading-relaxed text-muted">
      {text}
    </p>
  );
}

function RunMetric({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="bg-surface px-4 py-3">
      <div className="text-[0.62rem] font-bold uppercase tracking-[0.1em] text-subtle">{label}</div>
      <div className={clsx("numeric mt-1 text-sm font-bold capitalize text-ink", tone)}>{String(value).replace(/_/g, " ")}</div>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="card-muted min-w-[94px] px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-subtle">
        <Icon size={12} />
        <span className="text-[0.58rem] font-bold uppercase tracking-[0.1em]">{label}</span>
      </div>
      <div className={clsx("numeric display-font mt-1 text-lg font-bold", tone ?? "text-ink")}>{value}</div>
    </div>
  );
}
