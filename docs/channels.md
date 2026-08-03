# Simulation channels

BreachSim runs five attack channels through one pipeline. Every channel produces the same
artefacts — a `DeliveryAttempt`, a single-use `LandingToken`, and an event stream — so
analytics, risk scoring, remediation and reporting stay channel-agnostic. What differs is
the payload each adapter builds and whether anything leaves the platform.

| Channel | Outbound action | Employee entry point | Provider needed |
|---|---|---|---|
| Email | SMTP send to an allowlisted mailbox | `/training/<token>` | Any SMTP account |
| SMS | REST send to an allowlisted number | `/training/<token>` | Paid SMS gateway |
| QR | none — a poster is rendered for print | `/qr/<token>` | none |
| Voice (vishing) | none — runs in the browser; real cloned voice if configured | `/call/<token>` | ElevenLabs (optional) |
| Deepfake | none — runs in the browser; real cloned voice+video if configured | `/impersonation/<token>` | ElevenLabs + D-ID (optional) |

## Real cloned media

Voice and deepfake simulations render **real cloned media** when a provider is configured:

- **Voice** — ElevenLabs clones a consented persona's voice from a short sample and
  synthesizes the exact call/message text in that voice.
- **Video** — D-ID animates a consented face image to speak the cloned audio, producing a
  talking-head clip.

Both are pluggable behind `app/services/media/` and selected from configuration. With **no
provider configured, the simulators fall back to the browser Web Speech engine**, so the
platform still runs end to end at zero cost — realism degrades, the exercise does not break.

### The safety boundary is consent, not blur

Realism is the point of an enterprise deepfake drill — a cloned executive voice saying the
exact pretext is what makes the exercise land. The boundary is therefore not "keep it fake-
looking"; it is **provenance and lifecycle**:

- A voice or face can only be enrolled for a persona registered as a **real person with a
  signed consent reference** (see the consent registry below).
- Enrolment and generation are gated by the same second-admin approval and org-level switch
  as every other impersonation use.
- Every generated clip is stored as a `MediaAsset` with a **retention clock** — the sooner of
  the platform default and the persona's consent expiry — and swept when it passes.
- Clips are served only via a **single-use, unguessable access token**, never a predictable
  path, and marked `no-store`.
- **Revocation is destructive and immediate**: it deletes every stored clip *and* retires the
  enrolled voice at the provider, so the likeness can no longer be synthesized anywhere.

Voice can also be delivered over a real telephony provider if an organization wants genuine
outbound calls; the in-browser simulator is the default.

## Interactive simulations

Email, SMS and QR present one decision: click or report. Voice and deepfake are conversations
with escalating pressure, so they use a branching script.

```
GET  /api/v1/public/simulation/{token}            -> framing + the current step only
POST /api/v1/public/simulation/{token}/respond    -> record one decision, return the follow-up
POST /api/v1/public/simulation/{token}/complete   -> debrief and outcome summary
```

The full script is never sent to the browser. `load_simulation` returns only the step the
employee is currently on, and strips `risk_weight`, `safe` and `event_type` from the options,
so the correct answer cannot be read out of the network response before the decision is made.

Each decision is persisted as a `SimulationResponse` row, which is what lets the campaign
report show *where* in the pressure sequence somebody complied rather than just pass/fail.

### Outcome classification

| Outcome | Meaning |
|---|---|
| `resilient` | Took protective action, never complied |
| `recovered` | Complied early, then caught it |
| `compromised` | Complied and never corrected |
| `abandoned` | Left without completing |

## Content generation

The language model is only ever asked for the *narrative* fields — the pretext, the opening
line, the transcript. The branching structure, the safe options, the scoring weights and the
red-flag debrief are assembled deterministically in `app/services/channel_content.py`.

This keeps a simulation safe and consistent regardless of which provider is configured, and
means the platform works fully with no LLM configured at all (the built-in rule-based
generator produces every channel, including the branching scripts).

## Impersonation governance

Voice and deepfake simulations imitate somebody. That is the feature, and it is also the risk.
Three independent gates must all pass before a scenario can be generated:

1. **Policy** — the channel is switched on in *Governance → Controls*. New capabilities ship
   disabled so an upgrade never silently widens what an organization runs.
2. **Organization switch** — synthetic media is enabled in *Workspace Settings → Impersonation*.
3. **Persona** — an `ImpersonationPersona` that is approved, in-consent and modality-compatible.

Personas come in two kinds:

- **Synthetic composite role** (`is_real_person = false`) — e.g. "Finance Director". No
  individual is imitated, so only second-admin approval is required.
- **Real person** (`is_real_person = true`) — requires a signed consent reference and a
  mandatory expiry date. Consent that lapses automatically flips the persona to `expired`
  and blocks every scenario using it.

Approval must come from a different administrator than the one who registered the persona.
Revocation is immediate and irreversible; a revoked persona cannot be re-approved.

## Risk weighting

Interactive-channel failures are weighted above a link click because acting on a call or on
synthetic media bypasses every technical control the organization has — there is no gateway,
filter or sandbox between the attacker and the decision.

| Event | Weight |
|---|---|
| `trusted_synthetic_media` | +45 |
| `submitted_form_boolean` | +40 |
| `disclosed_on_call` | +35 |
| `clicked_link` | +20 |
| `replied_sms` | +18 |
| `scanned_qr` | +15 |
| `flagged_synthetic_media` | −30 |
| `verified_out_of_band` | −25 |
| `clicked_report` | −25 |
| `ended_call_safely` | −22 |
| `verified_caller` | −20 |

## Rate metrics

Failure and resilience rates are computed over distinct **people**, not events. An interactive
simulation records several decisions per target, so an event-over-delivery ratio would exceed
100% and make channels incomparable. Someone who both complied and resisted counts as a
failure, not as resilience.
