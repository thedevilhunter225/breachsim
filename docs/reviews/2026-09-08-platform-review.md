# Platform review and frontend refresh — 8 September 2026

## Assessment

BreachSim is a working local demonstration with a substantial application foundation.
The current installation is not ready for an enterprise launch. A healthy API and
passing behavioral tests do not establish that customer identity, delivery, public
domains, capacity, or recovery have been configured and verified.

This review used the local application and repository. It did not launch campaigns,
send mail, submit employee data to external providers, or change credentials.

## Observed launch gaps

| Finding | Evidence | Required follow-up |
| --- | --- | --- |
| Default signing secret in the running local configuration | API startup explicitly warns that `SECRET_KEY` is the shipped default or too short. | Configure a strong secret through the deployment secret store before exposing the API. |
| Enterprise onboarding is incomplete | Settings reports 1 of 6 readiness controls: only the managed landing domain is active. Recipient/sender domains, a healthy customer mail connection, SSO and SCIM are not configured. | Complete and validate customer onboarding against a test tenant. |
| Landing address is local | The configured active landing hostname is `localhost:3000`. | Configure a verified public HTTPS hostname for use from recipient devices. |
| Backend coverage gate fails | All 93 tests pass, but branch-inclusive coverage is 70.42%, below the existing 75% requirement. | Add meaningful tests around identity, tenant provisioning and worker behavior. Do not lower the threshold just to pass CI. |
| Deployment and scale are not established by this run | The reviewed runtime is a single-machine local API and frontend with an existing demo database. | Verify delivery/reconciliation, load, backups and recovery in the intended hosted environment. Existing runbooks document the remaining gates. |

Historic dashboard deliveries and sandbox events are retained demonstration records.
They do not prove that an external provider is currently connected or mail reaches an inbox.

## Frontend changes

- Added a common workspace design: neutral surfaces, compact navy navigation,
  consistent typography, restrained charts, readable tables and clear page headings.
- Rebuilt the overview around actual workspace metrics, department exposure,
  current risk distribution and explicitly labeled historical channel records.
- Replaced unconditional operational/live badges and the inactive notification
  control with accurate context and a working activity-log link.
- Added page search with Ctrl/Cmd+K, native modal focus handling, Escape dismissal,
  mobile navigation and a skip-to-content link.
- Improved employee search, department filtering, empty results, and loading/error states.
- Standardized settings navigation and page headers across the operator consoles.
- Corrected status presentation: draft/cancelled states are neutral, unknown/pending
  states use a caution treatment, and only actual failure/revocation states use red.
- Added retry states for overview, employee directory, analytics, audit and campaign
  records. A failed overview refresh retains the last loaded metrics.
- Kept the existing minimal login and authentication flows; workspace CSS is scoped
  away from participant training pages.

## Verification

- Backend lint: passed. Backend tests: 93 passed; coverage gate failed as noted above.
- Frontend lint and TypeScript checks: passed.
- Optimized production build: passed. The standalone frontend is running locally
  at `http://127.0.0.1:3000`; the API remains bound to `127.0.0.1:8000`.
- Existing frontend security tests and their configured coverage gate: passed.
  These two tests cover the security utility, not the entire interface.
- Browser checks: operator sign-in, overview, people, campaigns, scenario library,
  analytics, risk insights, reports, audit, policies, personas and settings.
- Directory search: no-result message and clear-filters action; Finance department
  filter returned the matching record.
- Page-search navigation, mobile drawer close-on-navigation, light/dark themes,
  and 390px mobile layout checks completed. Main pages did not overflow the viewport.
- Optimized-build checks also verified login/logout, password visibility, the MFA
  disclosure, Ctrl+K search, Escape dismissal, and exclusion of platform-operator
  navigation for the demo administrator. Tested production pages logged no browser errors.
- Browser-only offline simulation: refresh failure is visible and existing metrics
  remain available; network emulation was restored immediately afterward.

The platform-operator console was restyled through the shared design but was not
exercised with elevated platform-operator credentials in this review.
