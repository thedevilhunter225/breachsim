# BreachSim — feature list

Verified against a running instance with `python scripts/verify_channels.py`
(16 capabilities working, 0 failing, 1 optional provider outstanding) and
`python -m pytest tests` (32 passing).

**Scale:** 5 channels · 74 API endpoints · 29 database tables · 19 event types ·
18 frontend routes · 39 automated tests · real ElevenLabs/D-ID cloning behind a pluggable
provider layer.

---

## 1. Simulation channels

| # | Feature | Status | Notes |
|---|---|---|---|
| 1.1 | **Email phishing** | Working | SMTP send to allowlisted mailboxes, tracked link |
| 1.2 | **SMS / smishing** | Working (sandbox) | Full pipeline; **real carrier send needs a paid gateway** |
| 1.3 | **QR phishing** | Working | Printable poster, tracked scan code, downloadable PNG |
| 1.4 | **Voice / vishing** | Working | Branching call, spoofed caller ID, in-browser speech |
| 1.5 | **Deepfake impersonation** | Working | Voice-note or video message from a consented persona |

### Interactive simulation engine (voice + deepfake)

| # | Feature | Status |
|---|---|---|
| 1.6 | Branching multi-step script with escalating pressure | Working |
| 1.7 | Caller pushes back when the target tries to verify | Working |
| 1.8 | Step-by-step decision persistence (`SimulationResponse`) | Working |
| 1.9 | Answer key withheld from the client (no leaked `safe`/`risk_weight`) | Working |
| 1.10 | Replay protection — a step cannot be answered twice (HTTP 409) | Working |
| 1.11 | Browser speech synthesis playback (zero-cost fallback) | Working |
| 1.12 | Ringing screen, live call timer, transcript, mute | Working |
| 1.13 | Talking-head video frame (real clip, or abstract avatar fallback) | Working |
| 1.14 | Synthetic-media tells, revealed per difficulty level | Working |
| 1.15 | Outcome classification: resilient / recovered / compromised / abandoned | Working |
| 1.16 | Debrief showing the exact step where the target complied | Working |

### Real synthetic-media cloning

| # | Feature | Status |
|---|---|---|
| 1.17 | Pluggable media provider layer (mirrors the LLM layer) | Working |
| 1.18 | **ElevenLabs voice cloning** from a consented sample | Working (needs key) |
| 1.19 | Cloned-voice speech synthesis of the exact call/message text | Working (needs key) |
| 1.20 | **D-ID talking-head video** from a consented face + cloned audio | Working (needs key) |
| 1.21 | Graceful fallback to browser speech when no provider is configured | Working |
| 1.22 | Consent-gated enrolment — real voice/face only for a consented persona | Working |
| 1.23 | Generated clips bound to a scenario version (reused, not re-billed) | Working |
| 1.24 | Retention clock on every clip (min of platform default and consent expiry) | Working |
| 1.25 | Single-use token-gated serving, `no-store` | Working |
| 1.26 | Revocation deletes all clips and retires the provider-side voice | Working |
| 1.27 | Async video render with pending-poll on fetch | Working |
| 1.28 | Media provider status surfaced in Settings and Personas | Working |

---

## 2. AI scenario generation

| # | Feature | Status |
|---|---|---|
| 2.1 | Pluggable providers: Ollama, OpenAI, Gemini | Working |
| 2.2 | Deterministic rule-based generator — **works with no LLM at all** | Working |
| 2.3 | Automatic fallback when a provider errors or returns invalid JSON | Working |
| 2.4 | Channel-aware content (email body, SMS copy, QR poster, call script, transcript) | Working |
| 2.5 | LLM supplies narrative only; branch structure and scoring built deterministically | Working |
| 2.6 | Employee-context personalisation (role, department, approved profile) | Working |
| 2.7 | Persuasion-trigger detection and difficulty scoring (0–100) | Working |
| 2.8 | Placeholder/URL scrubbing from generated copy | Working |
| 2.9 | Scenario versioning with full edit history | Working |
| 2.10 | Landing-copy safety normalisation (never instructs real credential entry) | Working |

---

## 3. Governance and guardrails

| # | Feature | Status |
|---|---|---|
| 3.1 | Policy engine enforced **server-side before generation** | Working |
| 3.2 | Per-channel permission toggles (new capabilities ship disabled) | Working |
| 3.3 | Allowed-theme catalogue with custom themes | Working |
| 3.4 | Prohibited words and topics — hard block, not a warning | Working |
| 3.5 | Approved training domains | Working |
| 3.6 | Working-hours window and per-employee frequency cap | Working |
| 3.7 | Two-person rule on campaign approval | Working |
| 3.8 | Policy versioning with snapshots | Working |
| 3.9 | Employee opt-out respected | Working |

### Impersonation consent registry

| # | Feature | Status |
|---|---|---|
| 3.10 | Persona registry — nothing outside it can be impersonated | Working |
| 3.11 | Second-admin approval (creator cannot approve their own persona) | Working |
| 3.12 | Synthetic composite roles vs. real people, handled differently | Working |
| 3.13 | Signed consent reference mandatory for a real person | Working |
| 3.14 | Consent expiry — lapsed consent auto-expires and blocks all use | Working |
| 3.15 | Immediate, irreversible revocation | Working |
| 3.16 | Modality compatibility (a video persona cannot be used on a call) | Working |
| 3.17 | Organization-level master switch for synthetic media | Working |
| 3.18 | Encrypted consent evidence notes | Working |

---

## 4. Campaign operations

| # | Feature | Status |
|---|---|---|
| 4.1 | Campaign composer with multi-select targeting | Working |
| 4.2 | Dual-approval workflow (request → approve → second approve) | Working |
| 4.3 | Sandbox preview — full pipeline with nothing sent | Working |
| 4.4 | Channel-agnostic delivery dispatch | Working |
| 4.5 | Per-channel admin previews (email, SMS, QR poster, call, media) | Working |
| 4.6 | Copyable tokenized entry links per channel | Working |
| 4.7 | Recipient allowlists on email and SMS | Working |
| 4.8 | Graceful degradation to labelled sandbox when no provider is enabled | Working |
| 4.9 | Single-use expiring landing tokens (30-day TTL) | Working |
| 4.10 | Per-target failure isolation (one bad send does not abort the campaign) | Working |
| 4.11 | Delivery attempt ledger | Working |
| 4.12 | Campaign pause | Working |

---

## 5. Risk scoring and analytics

| # | Feature | Status |
|---|---|---|
| 5.1 | Weighted risk scoring across 19 event types | Working |
| 5.2 | Interactive-channel failures weighted above link clicks | Working |
| 5.3 | Protective actions reduce risk (verify, report, hang up, flag) | Working |
| 5.4 | Repeat-failure penalty and improvement credit | Working |
| 5.5 | Risk score history per employee | Working |
| 5.6 | Department aggregation and exposure ranking | Working |
| 5.7 | Per-channel failure and resilience rates (**computed per person, not per event**) | Working |
| 5.8 | Risk banding with severity colour-coding | Working |
| 5.9 | Weekly event-volume trend | Working |
| 5.10 | Adaptive recommendations: weakest channel, triggers, next theme, retest window | Working |
| 5.11 | Estimated fall likelihood, priority and confidence scoring | Working |
| 5.12 | Cold-start recommendations from role context | Working |

---

## 6. Training and remediation

| # | Feature | Status |
|---|---|---|
| 6.1 | Automatic micro-training assignment on compliance | Working |
| 6.2 | Channel-specific modules incl. voice and synthetic media | Working |
| 6.3 | Failure-reason classification driving module selection | Working |
| 6.4 | Completion tracking with dwell time | Working |
| 6.5 | Retest scheduling (14-day default) | Working |
| 6.6 | Post-simulation debrief with verification procedure | Working |

---

## 7. Reporting and evidence

| # | Feature | Status |
|---|---|---|
| 7.1 | Campaign evidence pack — print-ready HTML | Working |
| 7.2 | Per-employee outcome CSV | Working |
| 7.3 | Audit log CSV export | Working |
| 7.4 | Authorization chain in report (who created, who approved) | Working |
| 7.5 | Impersonation authorization section (persona, consent window) | Working |
| 7.6 | Interaction decision trail with timings | Working |
| 7.7 | Authenticated blob download (bearer token, not a bare link) | Working |
| 7.8 | Export registry | Working |

---

## 8. Directory and employees

| # | Feature | Status |
|---|---|---|
| 8.1 | Employee CRUD with department assignment | Working |
| 8.2 | Bulk import with per-row error reporting | Working |
| 8.3 | Consent status lifecycle | Working |
| 8.4 | Approved context profiles for personalisation | Working |
| 8.5 | Field-level encryption (phone, context, consent notes) | Working |
| 8.6 | Per-employee risk report with history and event timeline | Working |
| 8.7 | Employee self-service portal (history, opt-out, redaction request) | Working |

---

## 9. Security and privacy

| # | Feature | Status |
|---|---|---|
| 9.1 | JWT authentication with expiry | Working |
| 9.2 | Role-based access control (admin, manager, auditor, employee) | Working |
| 9.3 | Organization-scoped queries throughout | Working |
| 9.4 | Append-only audit log | Working |
| 9.5 | Access logging on sensitive reads | Working |
| 9.6 | Pseudonymous event identifiers | Working |
| 9.7 | Fernet field-level encryption at rest | Working |
| 9.8 | Security headers (nosniff, DENY framing, referrer policy) | Working |
| 9.9 | No credential capture anywhere in the platform | By design |
| 9.10 | Cloned media only from a consented, second-admin-approved persona | Working |
| 9.11 | Cloned media retention-bound and destroyed on consent revocation | Working |
| 9.12 | Media served by single-use token, never a predictable path | Working |
| 9.13 | Simulator pages excluded from search indexing | Working |

---

## 10. Platform and tooling

| # | Feature | Status |
|---|---|---|
| 10.1 | Docker Compose stack (API, frontend, Postgres, Redis, worker) | Working |
| 10.2 | Alembic migrations incl. Postgres enum extension | Working |
| 10.3 | SQLite auto-upgrade path with column backfill | Working |
| 10.4 | Redis + RQ background worker | Working |
| 10.5 | Light and dark themes | Working |
| 10.6 | Responsive layout with mobile navigation | Working |
| 10.7 | `scripts/demo_seed.py` — one-command five-channel demo | Working |
| 10.8 | `scripts/verify_channels.py` — end-to-end capability check | Working |
| 10.9 | `scripts/capture_screenshots.py` — report screenshots via headless Chrome | Working |
| 10.10 | 32 automated backend tests | Working |

---

## Requires a paid third-party service

**Only one item, and it is optional.**

| Capability | Service | Without it |
|---|---|---|
| Real outbound SMS | Twilio-compatible gateway | SMS runs as a labelled sandbox preview — content, tracking, scoring and reporting all still work |

Optional realism upgrades, none required:

| Capability | Service | Without it |
|---|---|---|
| Higher-realism copy | OpenAI / Gemini API key | Built-in generator produces all five channels |
| Real outbound calls | Telephony provider | In-browser voice simulator (the recommended path) |
| Real email delivery | Any SMTP account (free) | Sandbox preview |

**Voice and deepfake need no paid service at all** — they are rendered locally in the
target's browser by design, which is both cheaper and safer than a voice-cloning API.
