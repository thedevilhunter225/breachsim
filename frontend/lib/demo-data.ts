export const demoUser = {
  full_name: "Aisha Rahman",
  roles: ["admin"],
};

export const demoDashboard = {
  kpis: [
    { label: "Total Campaigns", value: 12 },
    { label: "Delivery Success", value: 97.1 },
    { label: "Click Rate", value: 18.4 },
    { label: "Report Rate", value: 41.2 },
  ],
  risk_distribution: [
    { band: "0-25", count: 14 },
    { band: "26-50", count: 21 },
    { band: "51-75", count: 10 },
    { band: "76-100", count: 5 },
  ],
  channel_performance: [
    { channel: "email", delivered: 68, clicks: 12, reports: 28 },
    { channel: "qr", delivered: 24, clicks: 6, reports: 7 },
    { channel: "sms", delivered: 16, clicks: 4, reports: 5 },
    { channel: "vishing", delivered: 0, clicks: 0, reports: 0 },
  ],
  vulnerable_departments: [
    { department: "Finance", avg_risk_score: 54, click_rate: 22, report_rate: 38, improvement_score: 46 },
    { department: "Sales", avg_risk_score: 48, click_rate: 20, report_rate: 34, improvement_score: 52 },
    { department: "Operations", avg_risk_score: 43, click_rate: 17, report_rate: 41, improvement_score: 57 },
    { department: "HR", avg_risk_score: 35, click_rate: 11, report_rate: 48, improvement_score: 65 },
  ],
  trend: [
    { date: "2026-03-11T00:00:00Z", value: 12 },
    { date: "2026-03-12T00:00:00Z", value: 19 },
    { date: "2026-03-13T00:00:00Z", value: 16 },
    { date: "2026-03-14T00:00:00Z", value: 23 },
    { date: "2026-03-15T00:00:00Z", value: 14 },
    { date: "2026-03-16T00:00:00Z", value: 28 },
    { date: "2026-03-17T00:00:00Z", value: 18 },
  ],
};

export const demoEmployees = Array.from({ length: 12 }).map((_, index) => {
  const departments = ["Finance", "HR", "IT", "Sales", "Operations"];
  const dept = departments[index % departments.length];
  return {
    id: `emp-${index + 1}`,
    employee_id: `EMP-${1000 + index}`,
    full_name: ["Amina Khan", "Bilal Ahmed", "Sana Malik", "Noor Raza"][index % 4] + ` ${index + 1}`,
    email: `employee${index + 1}@northwind.example.com`,
    phone: "+923001234567",
    role_title: `${dept} Specialist`,
    approved_context_summary: `Approved ${dept.toLowerCase()} workflow and internal communication notes.`,
    consent_status: index % 4 === 0 ? "pending" : "consented",
    risk_score: 18 + index * 4,
    status: "active",
    department_name: dept,
    latest_context_profile: {
      employee_context_profile: `Safe context profile for ${dept} role, using only approved internal notes.`,
      likely_scenario_themes: dept === "Finance" ? ["invoice/payment approval", "document review"] : ["policy update", "document review"],
      allowed_channels: ["email", "qr", "sms"],
      sensitivity_tags: ["role-relevance"],
    },
  };
});

export const demoPolicy = {
  name: "Default BreachSim Guardrails",
  allowed_themes: ["invoice/payment approval", "policy update", "leave request", "password reset", "mfa notice", "client contract", "quote request", "document review", "qr verification"],
  prohibited_words: ["arrest", "wire transfer", "hospital", "lawsuit"],
  allowed_sender_names: ["BreachSim Training", "Security Awareness Team", "Northwind IT", "HR Operations"],
  approved_training_domains: ["training.breachsim.local"],
  allowed_delivery_channels: ["email", "sms", "qr", "vishing"],
  difficulty_levels: ["low", "medium", "high"],
  maximum_frequency_per_employee: 2,
  working_hours_start: 9,
  working_hours_end: 18,
  second_approval_required: true,
  opt_out_respected: true,
  prohibited_topics: ["health emergency deception", "law enforcement impersonation", "real credential capture"],
};

export const demoScenarios = [
  {
    id: "scenario-1",
    title: "Invoice/Payment Approval: review requested",
    channel: "email",
    theme: "invoice/payment approval",
    difficulty_level: "medium",
    status: "approved",
    detected_persuasion_triggers: ["authority", "role-relevance"],
    policy_validation: { passed: true, warnings: ["Content includes explicit training labeling."] },
    latest_version: {
      subject: "Invoice/Payment Approval: review requested",
      body_copy: "Hello Amina, this internal training simulation references a finance workflow approval. Pause, inspect the request, and use the safe review path only.",
      cta_text: "Review Securely",
      landing_page_copy: "Training simulation only. No real credentials are stored.",
      rationale_metadata: { theme: "invoice/payment approval", channel: "email" },
      detected_persuasion_triggers: ["authority", "role-relevance"],
      difficulty_score: 52,
      validation_result: { passed: true, warnings: [] }
    }
  }
];

export const demoCampaigns = [
  {
    id: "camp-1",
    name: "Quarterly Finance Awareness Drill",
    description: "Finance team phishing simulation with review and micro-training.",
    channel: "email",
    campaign_type: "one_time",
    status: "approved",
    schedule_at: "2026-03-18T09:00:00Z",
    throttling_per_hour: 25,
    requires_second_approval: true,
    sandbox_mode: true,
    learning_objective: "Recognize finance-targeted approval lures.",
    target_count: 14,
    scenario_count: 1,
    target_filters: { department: "Finance" }
  }
];

export const demoDeliveryAttempts = [
  {
    id: "attempt-1",
    campaign_id: "camp-1",
    employee_id: "emp-1",
    channel: "email",
    status: "sandboxed",
    sandbox_mode: true,
    preview_payload: {
      subject: "Invoice/Payment Approval: review requested",
      preview_url: "/training/demo-token",
      cta_text: "Review Securely"
    }
  }
];

export const demoAuditLogs = [
  {
    id: "audit-1",
    action: "scenario.approve",
    resource_type: "scenario",
    resource_id: "scenario-1",
    details: { approver: "Aisha Rahman" },
    occurred_at: "2026-03-17T09:14:00Z"
  },
  {
    id: "audit-2",
    action: "campaign.launch_sandbox",
    resource_type: "campaign",
    resource_id: "camp-1",
    details: { attempt_count: 14 },
    occurred_at: "2026-03-17T09:20:00Z"
  }
];
