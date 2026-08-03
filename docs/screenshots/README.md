# Screenshots

Console and simulator captures for the report, poster and demo slides.

Regenerate any time with the backend and frontend running:

```bash
cd backend
python scripts/capture_screenshots.py --out ../docs/screenshots
python scripts/capture_screenshots.py --out ../docs/screenshots --theme dark
```

Captures are full-page at 1440 CSS px, 2× device scale (so they stay sharp when printed).

| File | Screen | Shows |
|---|---|---|
| `01-login.png` | Sign-in | Brand landing and admin sign-in |
| `02-dashboard.png` | Command Center | KPIs, event trend, risk composition, five-channel coverage |
| `03-scenario-studio.png` | Scenario Studio | Channel picker, persona selection, generated branching script |
| `04-campaigns.png` | Campaigns | Composer, dual approval, per-channel delivery previews |
| `05-personas.png` | Personas | Impersonation consent registry and org-level switch |
| `06-controls.png` | Controls | Channel and theme permissions, hard blocks, launch rules |
| `07-analytics.png` | Analytics | Event trend, risk banding, per-channel failure/resilience |
| `08-risk-intelligence.png` | Risk Intelligence | Department exposure and adaptive retest recommendations |
| `09-employees.png` | Directory | Employee list with risk scores |
| `10-reports.png` | Reports | Evidence packs per campaign, HTML and CSV export |
| `11-audit.png` | Audit Trail | Append-only activity record |
| `12-settings.png` | Workspace Settings | Email, SMS and impersonation provider configuration |
| `13-voice-incoming-call.png` | **Voice simulator** | Incoming call with spoofed caller ID |
| `14-deepfake-message.png` | **Deepfake simulator** | Synthetic video message and the comply-vs-verify decision |
| `15-simulation-debrief.png` | **Debrief** | Outcome, decision trail, breaking point, red flags, verification procedure |

To capture a simulator you need a live token. Run `python scripts/demo_seed.py`, copy the
printed entry point, then:

```bash
python scripts/capture_screenshots.py --out ../docs/screenshots --only __none__ \
  --extra "voice=http://localhost:3000/call/<token>"
```

Pass the full URL rather than a bare path — Git Bash on Windows rewrites a leading `/` into
a filesystem path.
