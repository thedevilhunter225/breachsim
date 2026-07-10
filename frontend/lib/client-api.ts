export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001/api/v1";

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
  latest_version?: ScenarioVersion | null;
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

export interface DashboardData {
  kpis: Array<{ label: string; value: number; delta?: number | null }>;
  risk_distribution: Array<{ band: string; count: number }>;
  channel_performance: Array<{ channel: string; delivered: number; clicks: number; reports: number }>;
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

export function getDeliveryAttempts(token: string) {
  return request<DeliveryAttempt[]>("/delivery-attempts", { headers: authHeaders(token) });
}

export function getAuditLogs(token: string) {
  return request<AuditLog[]>("/audit-logs", { headers: authHeaders(token) });
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
