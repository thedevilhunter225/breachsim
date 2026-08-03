export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001/api/v1";

/** Absolute URL for a public media clip served by its single-use access token. */
export function mediaUrl(token: string): string {
  return `${API_BASE}/public/media/${token}`;
}

export interface SessionUser {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  organization_id: string;
}

export interface SessionData {
  access_token: string;
  token_type: string;
  user: SessionUser;
}

export interface Department {
  id: string;
  name: string;
  code: string;
}

export interface OrganizationProfile {
  id: string;
  name: string;
  slug: string;
  timezone: string;
  retention_days: number;
  privacy_notice: string;
}

export interface ContextProfile {
  id: string;
  employee_context_profile: string;
  likely_scenario_themes: string[];
  allowed_channels: string[];
  sensitivity_tags: string[];
  created_at: string;
}

export interface Employee {
  id: string;
  employee_id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  role_title: string;
  approved_context_summary?: string | null;
  approved_public_profile_summary?: string | null;
  training_preferences: string[];
  consent_status: string;
  risk_score: number;
  status: string;
  department_id?: string | null;
  department_name?: string | null;
  latest_context_profile?: ContextProfile | null;
}

export interface EmployeeRiskHistoryPoint {
  date: string;
  score: number;
}

export interface EmployeeBehaviorSummary {
  opened_emails: number;
  clicked_links: number;
  visited_landing_pages: number;
  reported: number;
  submitted_forms: number;
  training_completed: number;
  last_event_at?: string | null;
}

export interface EmployeeReportEvent {
  id: string;
  event_type: string;
  channel?: string | null;
  occurred_at: string;
  metadata: Record<string, unknown>;
}

export interface EmployeeTrainingAssignment {
  id: string;
  status: string;
  assigned_reason_codes: string[];
  retest_scheduled_for?: string | null;
  module_title: string;
  module_body: string;
  guidance_points: string[];
}

export interface EmployeeRiskReport {
  employee: Employee;
  current_risk_score: number;
  trend: string;
  latest_breakdown: Record<string, number>;
  risk_history: EmployeeRiskHistoryPoint[];
  behavior_summary: EmployeeBehaviorSummary;
  events: EmployeeReportEvent[];
  training_assignments: EmployeeTrainingAssignment[];
}

export interface Policy {
  id: string;
  organization_id: string;
  name: string;
  allowed_themes: string[];
  prohibited_words: string[];
  allowed_sender_names: string[];
  approved_training_domains: string[];
  allowed_delivery_channels: string[];
  difficulty_levels: string[];
  maximum_frequency_per_employee: number;
  working_hours_start: number;
  working_hours_end: number;
  second_approval_required: boolean;
  opt_out_respected: boolean;
  prohibited_topics: string[];
}

/** One decision point in an interactive (voice or synthetic-media) simulation. */
export interface ScriptStep {
  key: string;
  index: number;
  speaker_line: string;
  pressure_tactic?: string | null;
  hint?: string | null;
  options: Array<{ key: string; label: string }>;
}

export interface SyntheticArtifact {
  key: string;
  label: string;
  detail: string;
  timestamp_hint?: string | null;
  revealed_upfront?: boolean;
}

export interface ChannelPayload {
  module?: string;
  channel?: string;
  header?: Record<string, any>;
  persona?: Record<string, any>;
  voice_profile?: Record<string, any>;
  transcript?: string;
  script?: Array<ScriptStep & { options: Array<Record<string, any>> }>;
  synthetic_artifacts?: SyntheticArtifact[];
  detection_tells?: string[];
  red_flags?: string[];
  verification_procedure?: string;
  debrief?: string;
  safety_notice?: string;
}

export interface ScenarioVersion {
  id: string;
  version_number: number;
  subject: string;
  body_copy: string;
  cta_text: string;
  landing_page_copy: string;
  rationale_metadata: Record<string, unknown>;
  detected_persuasion_triggers: string[];
  difficulty_score: number;
  validation_result: Record<string, unknown>;
  notes?: string | null;
  channel_payload?: ChannelPayload;
  created_at: string;
}

export interface Scenario {
  id: string;
  title: string;
  channel: string;
  theme: string;
  difficulty_level: string;
  status: string;
  detected_persuasion_triggers: string[];
  policy_validation: Record<string, unknown>;
  approved_at?: string | null;
  persona_id?: string | null;
  persona_display_name?: string | null;
  latest_version?: ScenarioVersion | null;
}

export type PersonaStatus = "draft" | "pending_consent" | "approved" | "revoked" | "expired";
export type MediaModality = "voice_note" | "voicemail" | "video_message" | "live_video_call";

export interface Persona {
  id: string;
  reference_code: string;
  display_name: string;
  role_title: string;
  relationship_to_targets: string;
  modality: MediaModality;
  status: PersonaStatus;
  is_real_person: boolean;
  linked_employee_id?: string | null;
  consent_reference?: string | null;
  consent_granted_at?: string | null;
  consent_expires_at?: string | null;
  revoked_at?: string | null;
  revocation_reason?: string | null;
  voice_profile: Record<string, any>;
  detection_tells: string[];
  synthetic_disclosure_text: string;
  usage_count: number;
  created_at: string;
  approved_by_user_id?: string | null;
  usable: boolean;
  voice_clone_provider?: string | null;
  voice_clone_ref?: string | null;
  has_face_image?: boolean;
}

/** Access tokens for real cloned media rendered for a scenario version. */
export interface SimulationMedia {
  audio_token?: string | null;
  video_token?: string | null;
  video_pending?: boolean;
}

/** Payload returned by the public simulation runtime, one step at a time. */
export interface SimulationState {
  token: string;
  module: string;
  channel: string;
  media?: SimulationMedia;
  campaign_name?: string | null;
  employee_first_name?: string | null;
  header: Record<string, any>;
  persona: Record<string, any>;
  voice_profile: Record<string, any>;
  transcript?: string | null;
  safety_notice?: string | null;
  total_steps: number;
  completed_steps: number;
  current_step?: ScriptStep | null;
  finished: boolean;
  scenario_title?: string | null;
  delivery_channel: string;
  visible_artifacts: SyntheticArtifact[];
}

export interface SimulationStepResult {
  recorded: boolean;
  outcome: "safe" | "unsafe" | "neutral";
  safe: boolean;
  followup_line?: string | null;
  coaching?: string | null;
  terminal: boolean;
  next_step?: ScriptStep | null;
  finished: boolean;
  assignment_id?: string | null;
  risk_score: number;
}

export interface SimulationSummary {
  token: string;
  outcome: "resilient" | "recovered" | "compromised" | "abandoned";
  headline: string;
  net_risk_weight: number;
  current_risk_score?: number | null;
  steps_taken: number;
  safe_actions: number;
  unsafe_actions: number;
  decision_trail: Array<{
    step_key: string;
    step_prompt: string;
    response_label: string;
    safe: boolean;
    risk_weight: number;
    elapsed_ms: number;
  }>;
  breaking_point?: { step_key: string; response_label: string } | null;
  red_flags: string[];
  detection_tells: string[];
  synthetic_artifacts: SyntheticArtifact[];
  verification_procedure?: string | null;
  debrief?: string | null;
  safety_notice?: string | null;
  scenario_title?: string | null;
  channel: string;
}

export interface Campaign {
  id: string;
  name: string;
  description?: string | null;
  channel: string;
  campaign_type: string;
  status: string;
  schedule_at?: string | null;
  throttling_per_hour: number;
  requires_second_approval: boolean;
  sandbox_mode: boolean;
  learning_objective: string;
  target_filters: Record<string, unknown>;
  target_count: number;
  scenario_count: number;
}

export interface DeliveryAttempt {
  id: string;
  campaign_id: string;
  employee_id: string;
  channel: string;
  status: string;
  sandbox_mode: boolean;
  preview_payload: Record<string, any>;
  delivered_at?: string | null;
}

export interface ChannelPerformance {
  channel: string;
  delivered: number;
  clicks: number;
  reports: number;
  risky_actions?: number;
  protective_actions?: number;
  failure_rate?: number;
  resilience_rate?: number;
}

export interface DashboardData {
  kpis: Array<{ label: string; value: number; delta?: number | null }>;
  risk_distribution: Array<{ band: string; count: number }>;
  channel_performance: ChannelPerformance[];
  vulnerable_departments: Array<{ department: string; avg_risk_score: number; click_rate: number; report_rate: number; improvement_score: number }>;
  trend: Array<{ date: string; value: number }>;
}

export interface BehaviorSignal {
  label: string;
  value: number;
}

export interface DepartmentBehaviorReport {
  department_id: string;
  department: string;
  employee_count: number;
  avg_risk_score: number;
  click_rate: number;
  report_rate: number;
  opened_email_rate: number;
  training_completion_count: number;
  risky_interactions: number;
  report_events: number;
  last_activity_at?: string | null;
  behavior_trend: Array<{ date: string; value: number }>;
  risk_trend: Array<{ date: string; value: number }>;
  top_behavior_signals: BehaviorSignal[];
}

export interface AdaptiveRecommendation {
  employee_id: string;
  employee_name: string;
  employee_email: string;
  department?: string | null;
  current_risk_score: number;
  weak_channel: string;
  weak_triggers: string[];
  recommended_theme: string;
  recommended_channel: string;
  recommended_difficulty: string;
  estimated_fall_likelihood: number;
  priority_score: number;
  confidence: number;
  risk_band: string;
  recommended_action: string;
  learning_objective: string;
  retest_window_days: number;
  reason_breakdown: Record<string, number>;
  rationale: string;
  evidence: string[];
}

export interface RiskIntelligenceData {
  overview: {
    monitored_employees: number;
    high_risk_employees: number;
    average_risk_score: number;
    improving_employees: number;
    departments_flagged: number;
  };
  department_reports: DepartmentBehaviorReport[];
  adaptive_recommendations: AdaptiveRecommendation[];
}

export interface AuditLog {
  id: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details: Record<string, unknown>;
  occurred_at: string;
}

export interface EmailIntegration {
  email_provider_enabled: boolean;
  email_provider_mode: string;
  smtp_host?: string | null;
  smtp_port: number;
  smtp_username?: string | null;
  smtp_from_email?: string | null;
  smtp_sender_name?: string | null;
  smtp_recipient_allowlist: string[];
  has_password: boolean;
}

export interface SmsIntegration {
  sms_provider_enabled: boolean;
  sms_provider_mode: string;
  sms_api_base_url?: string | null;
  sms_account_sid?: string | null;
  sms_from_number?: string | null;
  sms_recipient_allowlist: string[];
  has_auth_token: boolean;
}

export interface ImpersonationSettings {
  impersonation_enabled: boolean;
  impersonation_disclosure_text: string;
  approved_persona_count: number;
  voice_provider_enabled: boolean;
  voice_provider_mode: string;
  voice_clone_provider?: string;
  voice_clone_configured?: boolean;
  video_clone_provider?: string;
  video_clone_configured?: boolean;
}

export interface EmployeeImportResult {
  created: number;
  updated: number;
  errors: Array<Record<string, unknown>>;
}

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

export const AUTH_EXPIRED_EVENT = "breachsim.auth_expired";

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(payload?.detail ? JSON.stringify(payload.detail) : response.statusText, response.status, payload);
  }
  return payload as T;
}

function authHeaders(token: string, initHeaders?: HeadersInit): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(initHeaders ?? {}),
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...init, cache: "no-store" });
  return parseResponse<T>(response);
}

export function loginRequest(email: string, password: string) {
  return request<SessionData>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function getDashboard(token: string) {
  return request<DashboardData>("/analytics/dashboard", { headers: authHeaders(token) });
}

export function getRiskIntelligence(token: string) {
  return request<RiskIntelligenceData>("/analytics/risk-intelligence", { headers: authHeaders(token) });
}

export function getCurrentOrg(token: string) {
  return request<OrganizationProfile>("/orgs/current", { headers: authHeaders(token) });
}

export function updateCurrentOrg(token: string, payload: Record<string, unknown>) {
  return request<OrganizationProfile>("/orgs/current", {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function getEmployees(token: string) {
  return request<Employee[]>("/employees", { headers: authHeaders(token) });
}

export function getDepartments(token: string) {
  return request<Department[]>("/departments", { headers: authHeaders(token) });
}

export function createDepartment(token: string, payload: Record<string, unknown>) {
  return request<Department>("/departments", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function createEmployee(token: string, payload: Record<string, unknown>) {
  return request<Employee>("/employees", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function updateEmployee(token: string, employeeId: string, payload: Record<string, unknown>) {
  return request<Employee>(`/employees/${employeeId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function getEmployeeReport(token: string, employeeId: string) {
  return request<EmployeeRiskReport>(`/employees/${employeeId}/report`, {
    headers: authHeaders(token),
  });
}

export function importEmployees(token: string, payload: Record<string, unknown>) {
  return request<EmployeeImportResult>("/employees/import", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function getPolicy(token: string) {
  return request<Policy>("/policies/current", { headers: authHeaders(token) });
}

export function updatePolicy(token: string, payload: Record<string, unknown>) {
  return request<Policy>("/policies/current", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function getScenarios(token: string) {
  return request<Scenario[]>("/scenarios", { headers: authHeaders(token) });
}

export function generateScenario(token: string, payload: Record<string, unknown>) {
  return request<Scenario>("/scenarios/generate", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export interface DeletionResult {
  resource: string;
  resource_id: string;
  label: string;
  removed: Record<string, number>;
}

export function deleteScenario(token: string, scenarioId: string) {
  return request<DeletionResult>(`/scenarios/${scenarioId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

/** Deleting a campaign with recorded evidence requires an explicit purge. */
export function deleteCampaign(token: string, campaignId: string, purgeEvidence = false) {
  return request<DeletionResult>(
    `/campaigns/${campaignId}${purgeEvidence ? "?purge_evidence=true" : ""}`,
    { method: "DELETE", headers: authHeaders(token) },
  );
}

export function deleteEmployee(token: string, employeeId: string) {
  return request<DeletionResult>(`/employees/${employeeId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export function deleteDepartment(token: string, departmentId: string) {
  return request<DeletionResult>(`/departments/${departmentId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export function deletePersona(token: string, personaId: string) {
  return request<DeletionResult>(`/personas/${personaId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export function approveScenario(token: string, scenarioId: string) {
  return request<Scenario>(`/scenarios/${scenarioId}/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function editScenario(token: string, scenarioId: string, payload: Record<string, unknown>) {
  return request<Scenario>(`/scenarios/${scenarioId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function getCampaigns(token: string) {
  return request<Campaign[]>("/campaigns", { headers: authHeaders(token) });
}

export function createCampaign(token: string, payload: Record<string, unknown>) {
  return request<Campaign>("/campaigns", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function requestCampaignApproval(token: string, campaignId: string) {
  return request<Campaign>(`/campaigns/${campaignId}/request-approval`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function approveCampaign(token: string, campaignId: string) {
  return request<Campaign>(`/campaigns/${campaignId}/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function launchCampaignSandbox(token: string, campaignId: string) {
  return request<DeliveryAttempt[]>(`/campaigns/${campaignId}/launch-sandbox`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function deliverCampaignEmail(token: string, campaignId: string) {
  return request<DeliveryAttempt[]>(`/campaigns/${campaignId}/deliver-email`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

/** Channel-agnostic delivery: sends on email/SMS, activates the session elsewhere. */
export function deliverCampaign(token: string, campaignId: string) {
  return request<DeliveryAttempt[]>(`/campaigns/${campaignId}/deliver`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

/* ---------------------------------------------------------------- personas */

export function getPersonas(token: string) {
  return request<Persona[]>("/personas", { headers: authHeaders(token) });
}

export function createPersona(token: string, payload: Record<string, unknown>) {
  return request<Persona>("/personas", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function approvePersona(token: string, personaId: string) {
  return request<Persona>(`/personas/${personaId}/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function revokePersona(token: string, personaId: string, reason: string) {
  return request<Persona>(`/personas/${personaId}/revoke`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
}

export interface MediaProviderStatus {
  voice: { configured: boolean; provider: string; supports_cloning: boolean };
  video: { configured: boolean; provider: string; supports_talking_head: boolean };
  max_upload_mb: number;
  retention_days: number;
}

export function getMediaProviders(token: string) {
  return request<MediaProviderStatus>("/media/providers", { headers: authHeaders(token) });
}

/** Upload a consented voice sample and enrol it with the cloning provider. */
export async function uploadVoiceSample(token: string, personaId: string, file: File) {
  return uploadFile<{ asset_id: string; provider: string | null; cloned: boolean; voice_ref: string | null }>(
    token,
    `/personas/${personaId}/voice-sample`,
    file,
  );
}

/** Upload a consented face image for talking-head video. */
export async function uploadFaceImage(token: string, personaId: string, file: File) {
  return uploadFile<{ asset_id: string; has_face_image: boolean }>(
    token,
    `/personas/${personaId}/face-image`,
    file,
  );
}

async function uploadFile<T>(token: string, path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  // No Content-Type header: the browser sets the multipart boundary itself.
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    cache: "no-store",
  });
  return parseResponse<T>(response);
}

/* ------------------------------------------------- public simulation runtime
   These endpoints are intentionally unauthenticated: the tokenized link is the
   credential, exactly as the simulated message would be in the real world. */

export function getSimulation(simulationToken: string) {
  return request<SimulationState>(`/public/simulation/${simulationToken}`);
}

export function postSimulationResponse(
  simulationToken: string,
  payload: { step_key: string; response_key: string; elapsed_ms?: number },
) {
  return request<SimulationStepResult>(`/public/simulation/${simulationToken}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function completeSimulation(simulationToken: string) {
  return request<SimulationSummary>(`/public/simulation/${simulationToken}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

export function getDeliveryAttempts(token: string) {
  return request<DeliveryAttempt[]>("/delivery-attempts", { headers: authHeaders(token) });
}

export function getAuditLogs(token: string) {
  return request<AuditLog[]>("/audit-logs", { headers: authHeaders(token) });
}

export interface ReportableCampaign {
  id: string;
  name: string;
  channel: string;
  status: string;
  target_count: number;
  created_at: string;
}

export function getReportableCampaigns(token: string) {
  return request<ReportableCampaign[]>("/reports/campaigns", { headers: authHeaders(token) });
}

/**
 * Fetch an export with the bearer token attached and hand the browser a blob to save.
 * A plain anchor href cannot carry the Authorization header, so the download has to be
 * driven from script rather than markup.
 */
export async function downloadReport(
  token: string,
  path: string,
  filename: string,
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(`Export failed (${response.status})`, response.status, null);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoke on the next tick so the click has already been handled.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function getEmailIntegration(token: string) {
  return request<EmailIntegration>("/integrations/email", { headers: authHeaders(token) });
}

export function updateEmailIntegration(token: string, payload: Record<string, unknown>) {
  return request<EmailIntegration>("/integrations/email", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function getSmsIntegration(token: string) {
  return request<SmsIntegration>("/integrations/sms", { headers: authHeaders(token) });
}

export function updateSmsIntegration(token: string, payload: Record<string, unknown>) {
  return request<SmsIntegration>("/integrations/sms", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function getImpersonationSettings(token: string) {
  return request<ImpersonationSettings>("/integrations/impersonation", { headers: authHeaders(token) });
}

export function updateImpersonationSettings(token: string, payload: Record<string, unknown>) {
  return request<ImpersonationSettings>("/integrations/impersonation", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}
