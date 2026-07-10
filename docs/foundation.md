# BreachSim Foundation

## 1. Concise Architecture Summary

BreachSim is a multi-tenant SaaS phishing simulation platform built as a monorepo with a FastAPI backend, a Next.js frontend, PostgreSQL for relational data, Redis plus RQ for background jobs, and Docker for local orchestration. The backend owns RBAC, approved-context profiling, policy validation, scenario generation, campaign approvals, sandbox delivery, event tracking, explainable risk scoring, adaptive micro-training, audit logging, and report export. The frontend provides a production-style admin console, approval workflow, analytics views, and an optional employee self-view portal. Sensitive fields use field-level encryption, event analytics use pseudonymous IDs where possible, and every risky action is audited.

## 2. Folder Structure

```text
breachsim/
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── api/routes/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── utils/
│   │   └── workers/
│   ├── tests/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── (dashboard)/
│   │   ├── employee-portal/
│   │   └── training/[token]/
│   ├── components/
│   ├── lib/
│   ├── public/
│   ├── styles/
│   ├── next.config.mjs
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── api/
│   ├── architecture/
│   ├── demo/
│   ├── diagrams/
│   └── security/
├── infra/
├── sample_outputs/
├── docker-compose.yml
└── README.md
```

## 3. Database Schema

### Core tenancy and access

- `organizations`: company tenant, branding, retention defaults, timezone
- `users`: platform operators and optional employee portal users
- `roles`: seeded roles such as `admin`, `campaign_manager`, `auditor`, `employee`
- `user_roles`: many-to-many role assignment per organization
- `access_logs`: read access telemetry for sensitive resources

### Directory and privacy

- `departments`: department catalog for an organization
- `employees`: target directory with encrypted phone and approved context fields
- `consent_records`: consent state, legal basis note, opt-out timestamps, redaction requests
- `context_profiles`: approved-context-derived safe profile, theme suggestions, channel allowances, sensitivity tags

### Policy and content control

- `policies`: organization policy document with guardrails and scheduling rules
- `policy_versions`: append-only history of policy changes
- `scenarios`: generated scenario draft metadata and current status
- `scenario_versions`: immutable content revisions, manual edits, validation outcomes
- `failure_reasons`: normalized persuasion/failure taxonomy

### Campaign execution

- `campaigns`: high-level campaign entity, cadence, scheduling, throttling, approval requirements
- `campaign_targets`: employee or department targeting records
- `campaign_scenarios`: mapping from campaign to assigned scenario variants
- `delivery_attempts`: email/QR/SMS sandbox or lab-only send attempt log
- `landing_tokens`: tokenized tracking artifacts for click/scan journeys
- `event_logs`: normalized delivery and interaction events

### Training and risk

- `training_modules`: micro-training cards and retest guidance
- `training_assignments`: assignment state, source failure trigger, retest scheduling
- `training_completions`: completion and dwell metrics
- `risk_scores`: explainable score snapshots by employee, department, channel, and time bucket

### Governance and reporting

- `audit_logs`: append-only log for critical actions
- `report_exports`: generated export metadata and storage paths

### Indexing strategy

- Composite indexes on `(organization_id, status)` for campaigns, employees, scenarios
- Time-series indexes on `event_logs.occurred_at`, `risk_scores.calculated_at`
- Filter indexes for `delivery_attempts.channel`, `event_logs.event_type`
- Unique constraints on `employees.employee_id`, `users.email`, `landing_tokens.token`
- Foreign keys with cascading deletes only where safe; audit/history tables stay append-only

## 4. API Route Plan

### Auth and session

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`

### Organization and directory

- `GET /api/v1/orgs/current`
- `PATCH /api/v1/orgs/current`
- `GET /api/v1/departments`
- `POST /api/v1/departments`
- `GET /api/v1/employees`
- `POST /api/v1/employees`
- `POST /api/v1/employees/import`
- `GET /api/v1/employees/{employee_id}`
- `PATCH /api/v1/employees/{employee_id}`
- `POST /api/v1/employees/{employee_id}/consent`
- `POST /api/v1/employees/{employee_id}/profile`

### Policy, scenario, and review

- `GET /api/v1/policies/current`
- `PUT /api/v1/policies/current`
- `GET /api/v1/scenarios`
- `POST /api/v1/scenarios/generate`
- `GET /api/v1/scenarios/{scenario_id}`
- `PATCH /api/v1/scenarios/{scenario_id}`
- `POST /api/v1/scenarios/{scenario_id}/approve`
- `POST /api/v1/scenarios/{scenario_id}/reject`

### Campaigns and delivery

- `GET /api/v1/campaigns`
- `POST /api/v1/campaigns`
- `GET /api/v1/campaigns/{campaign_id}`
- `PATCH /api/v1/campaigns/{campaign_id}`
- `POST /api/v1/campaigns/{campaign_id}/request-approval`
- `POST /api/v1/campaigns/{campaign_id}/approve`
- `POST /api/v1/campaigns/{campaign_id}/launch-sandbox`
- `POST /api/v1/campaigns/{campaign_id}/pause`
- `GET /api/v1/delivery-attempts`

### Tracking and training

- `POST /api/v1/events/track`
- `GET /api/v1/training/modules`
- `GET /api/v1/training/assignments`
- `POST /api/v1/training/assignments/{assignment_id}/complete`

### Analytics and reporting

- `GET /api/v1/analytics/dashboard`
- `GET /api/v1/analytics/risk-distribution`
- `GET /api/v1/analytics/departments`
- `GET /api/v1/reports/audit`
- `GET /api/v1/reports/campaign/{campaign_id}`
- `POST /api/v1/reports/export`

### Governance and self-service

- `GET /api/v1/audit-logs`
- `GET /api/v1/access-logs`
- `GET /api/v1/employee-portal/me`
- `GET /api/v1/employee-portal/history`
- `POST /api/v1/employee-portal/opt-out`
- `POST /api/v1/employee-portal/redaction-request`

## 5. Phased Implementation Plan

### Phase 1

- Backend app bootstrap, config, database, auth, RBAC
- Organization, department, employee, consent, context profile models and routes
- Seed data and dashboard skeleton

### Phase 2

- Policy engine, scenario generator abstraction, structured scenario JSON
- Scenario versioning, admin review workflow, approval chain

### Phase 3

- Campaign entity, sandbox delivery adapters, landing tokens, training landing flows
- Event tracking, delivery telemetry, QR generation, SMS and vishing prototype placeholders

### Phase 4

- Failure reason classification, explainable risk scoring, adaptive micro-training assignment
- Retest scheduling, analytics aggregations, risk trends

### Phase 5

- Audit and access logs, employee portal, exports, threat model, demo script, tests, polish
