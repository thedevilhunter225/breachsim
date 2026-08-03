# BreachSim Architecture Overview

BreachSim follows a clean service-oriented monolith design for the MVP. The FastAPI backend exposes a versioned REST API and contains domain services for policy enforcement, scenario generation, sandbox delivery, event ingestion, risk analytics, micro-training assignment, and governance controls. Background jobs are queued through Redis and processed by an RQ worker for delivery simulation, report export, and deferred retest scheduling. PostgreSQL is the source of truth for transactional and analytical tables. The Next.js frontend consumes the REST API through a thin typed client layer and renders admin, analyst, manager, and employee experiences.

Key design choices:

- Multi-tenant but single-organization demo seed to keep the FYP demo simple.
- AI generation is mediated by a strict policy validation layer; invalid content is blocked or regenerated.
- All delivery adapters are sandbox-first and provider integrations remain disabled by default.
- Sensitive employee context is encrypted at the field level, while event analytics prefer pseudonymous identifiers.
- Auditability is first-class: approval flow, policy changes, data access, and export actions are append-only logged.

## Channel layer

Five channels — email, SMS, QR, voice (vishing) and synthetic-media impersonation (deepfake) —
share one pipeline. Each delivery adapter emits the same artefacts (`DeliveryAttempt`,
`LandingToken`, `delivered` event) so analytics, scoring, remediation and reporting remain
channel-agnostic; only the payload and the outbound behaviour differ.

Email and SMS send outbound to allowlisted recipients. QR, voice and deepfake are *pull*
channels: nothing leaves the platform, and the simulation is rendered in the target's browser
from an approved script. No call is placed and no media file is generated or stored.

Voice and deepfake are conversations rather than single-decision lures, so they carry a
branching interaction script. Each decision is persisted as a `SimulationResponse`, which is
what lets a campaign report show *where* in the pressure sequence somebody complied.

The language model supplies only narrative fields; the branch structure, safe options and
scoring weights are assembled deterministically, so a bad model response cannot make a
simulation unsafe and the platform stays fully functional with no LLM configured.

## Impersonation governance

Because voice and deepfake imitate an identity, three independent gates must pass before a
scenario can be generated: the channel must be permitted by policy, synthetic media must be
enabled organization-wide, and the scenario must reference an `ImpersonationPersona` that is
approved by a second administrator and inside a live consent window. Personas representing a
real person require a signed consent reference and a mandatory expiry; lapsed consent
auto-expires the persona and blocks every scenario using it.

See [channels.md](../channels.md) for the full design.
