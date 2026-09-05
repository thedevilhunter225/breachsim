"""Provision a complete five-channel demo against a running BreachSim API.

Creates the governance objects a live demo needs (personas, policy scope) and then
runs one campaign per channel end to end, printing the tokenized employee entry point
for each so you can walk the flow on screen.

Usage::

    python scripts/demo_seed.py                       # against http://127.0.0.1:8000
    python scripts/demo_seed.py --base-url http://host:8000
    python scripts/demo_seed.py --run-interactive     # also answer the voice/deepfake sims

Nothing here bypasses the API: every guardrail (dual approval, persona consent,
policy scope) is exercised exactly as the console would exercise it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

ACCOUNTS = {
    "admin": ("admin@breachsim-lab.com", "Admin123!"),
    "reviewer": ("reviewer@breachsim-lab.com", "Reviewer123!"),
    "manager": ("manager@breachsim-lab.com", "Manager123!"),
}

CHANNEL_PLAN = [
    ("email", "invoice/payment approval", "medium", None),
    ("sms", "policy update", "medium", None),
    ("qr", "qr verification", "medium", None),
    ("vishing", "password reset", "high", "voice"),
    ("deepfake", "executive approval request", "high", "video"),
]

PERSONAS = {
    "voice": {
        "display_name": "IT Service Desk Lead",
        "role_title": "Service Desk Lead",
        "relationship_to_targets": "internal support",
        "modality": "voice_note",
        "is_real_person": False,
        "detection_tells": [
            "A real colleague will accept a call-back through the directory.",
            "Urgency tied to a deadline you cannot verify is the tell.",
        ],
    },
    "video": {
        "display_name": "Ayesha Malik",
        "role_title": "Group Finance Director",
        "relationship_to_targets": "senior leadership",
        "modality": "video_message",
        "is_real_person": False,
        "detection_tells": [
            "Recognition is not verification.",
            "Confirm high-value approvals on a channel you chose yourself.",
        ],
    },
}


class Api:
    def __init__(self, base_url: str) -> None:
        self.base = f"{base_url.rstrip('/')}/api/v1"
        self.client = httpx.Client(timeout=60.0)
        self.tokens: dict[str, str] = {}

    def login_all(self) -> None:
        for role, (email, password) in ACCOUNTS.items():
            response = self.client.post(
                f"{self.base}/auth/login",
                json={"email": email, "password": password},
                headers={"X-BreachSim-API-Client": "bearer"},
            )
            response.raise_for_status()
            self.tokens[role] = response.json()["access_token"]

    def call(self, method: str, path: str, role: str = "admin", **kwargs) -> Any:
        headers = {"Authorization": f"Bearer {self.tokens[role]}"}
        response = self.client.request(method, f"{self.base}{path}", headers=headers, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:400]}")
        return response.json() if response.content else None

    def public(self, method: str, path: str, **kwargs) -> Any:
        response = self.client.request(method, f"{self.base}{path}", **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:400]}")
        return response.json() if response.content else None


def step(message: str) -> None:
    print(f"  {message}")


def heading(message: str) -> None:
    print(f"\n\033[1m{message}\033[0m" if sys.stdout.isatty() else f"\n{message}")


def ensure_policy_scope(api: Api) -> None:
    heading("Policy scope")
    policy = api.call("GET", "/policies/current")
    wanted_channels = [channel for channel, *_ in CHANNEL_PLAN]
    wanted_themes = {theme for _, theme, *_ in CHANNEL_PLAN}

    changed = False
    for channel in wanted_channels:
        if channel not in policy["allowed_delivery_channels"]:
            policy["allowed_delivery_channels"].append(channel)
            changed = True
    for theme in wanted_themes:
        if theme not in policy["allowed_themes"]:
            policy["allowed_themes"].append(theme)
            changed = True

    if not changed:
        step("All five channels and demo themes already permitted.")
        return

    policy.pop("id", None)
    policy.pop("organization_id", None)
    api.call("PUT", "/policies/current", json=policy)
    step(f"Enabled channels: {', '.join(wanted_channels)}")


def ensure_impersonation(api: Api) -> None:
    heading("Impersonation settings")
    settings = api.call("GET", "/integrations/impersonation")
    if settings["impersonation_enabled"]:
        step("Synthetic media already enabled.")
        return
    api.call(
        "PUT",
        "/integrations/impersonation",
        json={
            "impersonation_enabled": True,
            "impersonation_disclosure_text": settings["impersonation_disclosure_text"],
            "voice_provider_enabled": False,
            "voice_provider_mode": "simulator",
        },
    )
    step("Synthetic media simulations enabled (in-browser simulator).")


def ensure_personas(api: Api) -> dict[str, str]:
    heading("Impersonation personas")
    existing = {persona["display_name"]: persona for persona in api.call("GET", "/personas")}
    resolved: dict[str, str] = {}

    for key, spec in PERSONAS.items():
        persona = existing.get(spec["display_name"])
        if persona and persona["usable"]:
            step(f"Reusing approved persona '{persona['display_name']}'.")
            resolved[key] = persona["id"]
            continue
        if persona:
            step(f"Persona '{persona['display_name']}' exists but is {persona['status']}; registering a fresh one.")

        payload = dict(spec)
        payload["consent_expires_at"] = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        created = api.call("POST", "/personas", role="admin", json=payload)
        # Approval must come from a different administrator than the creator.
        approved = api.call("POST", f"/personas/{created['id']}/approve", role="reviewer")
        step(f"Registered and approved '{approved['display_name']}' ({approved['modality']}).")
        resolved[key] = approved["id"]

    return resolved


def pick_employees(api: Api, count: int) -> list[dict]:
    employees = api.call("GET", "/employees", role="manager")
    if not employees:
        raise RuntimeError(
            "No employees in the directory. Start the API with SEED_DEMO_CONTENT=true, "
            "or import a directory first."
        )
    # Spread the campaigns across distinct people so risk deltas stay legible.
    return [employees[index % len(employees)] for index in range(count)]


def run_channel(api: Api, *, channel: str, theme: str, difficulty: str, persona_id: str | None, employee: dict) -> dict:
    heading(f"Channel: {channel}")
    step(f"Target: {employee['full_name']} ({employee.get('department_name') or 'Unassigned'})")

    scenario_payload = {
        "employee_id": employee["id"],
        "channel": channel,
        "theme": theme,
        "difficulty_level": difficulty,
        "prompt_instructions": "Keep it realistic and specific to this employee's workflow.",
    }
    if persona_id:
        scenario_payload["persona_id"] = persona_id

    scenario = api.call("POST", "/scenarios/generate", role="manager", json=scenario_payload)
    step(f"Generated scenario: {scenario['title']}")

    payload = (scenario.get("latest_version") or {}).get("channel_payload") or {}
    if payload.get("script"):
        step(f"Interaction script: {len(payload['script'])} decision points")

    api.call("POST", f"/scenarios/{scenario['id']}/approve", role="admin")

    campaign = api.call(
        "POST",
        "/campaigns",
        role="manager",
        json={
            "name": f"Demo · {channel} · {theme}",
            "description": f"Five-channel demo campaign for the {channel} vector.",
            "channel": channel,
            "target_employee_ids": [employee["id"]],
            "scenario_ids": [scenario["id"]],
            "requires_second_approval": False,
            "sandbox_mode": True,
        },
    )
    api.call("POST", f"/campaigns/{campaign['id']}/request-approval", role="manager")
    api.call("POST", f"/campaigns/{campaign['id']}/approve", role="admin")

    attempts = api.call("POST", f"/campaigns/{campaign['id']}/deliver", role="manager")
    attempt = attempts[0]
    entry = attempt["preview_payload"].get("entry_url") or attempt["preview_payload"].get("preview_url")
    step(f"Delivery status: {attempt['status']}")
    step(f"Employee entry point: {entry}")

    return {"channel": channel, "employee": employee, "attempt": attempt, "entry_url": entry}


def walk_interactive(api: Api, result: dict) -> None:
    """Answer an interactive simulation the unsafe way, then print the debrief."""
    entry = result["entry_url"]
    if not entry:
        return
    token = entry.rstrip("/").rsplit("/", 1)[-1]

    state = api.public("GET", f"/public/simulation/{token}")
    step(f"Simulation loaded: {state['total_steps']} steps, module {state['module']}")

    guard = 0
    while state.get("current_step") and guard < 10:
        guard += 1
        current = state["current_step"]
        # Choose the first option, which is always the compliant path — this is the
        # branch that demonstrates detection, scoring and remediation firing.
        choice = current["options"][0]
        outcome = api.public(
            "POST",
            f"/public/simulation/{token}/respond",
            json={"step_key": current["key"], "response_key": choice["key"], "elapsed_ms": 2500},
        )
        step(f"  step '{current['key']}' -> '{choice['label']}' ({outcome['outcome']})")
        if outcome.get("assignment_id"):
            step("  remediation training assigned")
        if outcome["finished"] or outcome["terminal"]:
            break
        state = {"current_step": outcome.get("next_step")}

    summary = api.public("POST", f"/public/simulation/{token}/complete")
    step(f"Outcome: {summary['outcome']} — {summary['headline']}")
    step(f"Risk score now {summary['current_risk_score']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL (default: %(default)s)")
    parser.add_argument(
        "--run-interactive",
        action="store_true",
        help="Also walk the voice and deepfake simulations to completion.",
    )
    args = parser.parse_args()

    api = Api(args.base_url)
    try:
        api.login_all()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not sign in against {args.base_url}: {exc}")
        print("Is the API running? Try: uvicorn app.main:app --port 8000")
        return 1

    heading("BreachSim five-channel demo provisioning")
    step(f"API: {api.base}")

    ensure_policy_scope(api)
    ensure_impersonation(api)
    personas = ensure_personas(api)

    employees = pick_employees(api, len(CHANNEL_PLAN))
    results = []
    for index, (channel, theme, difficulty, persona_key) in enumerate(CHANNEL_PLAN):
        persona_id = personas.get(persona_key) if persona_key else None
        results.append(
            run_channel(
                api,
                channel=channel,
                theme=theme,
                difficulty=difficulty,
                persona_id=persona_id,
                employee=employees[index],
            )
        )

    if args.run_interactive:
        for result in results:
            if result["channel"] in {"vishing", "deepfake"}:
                heading(f"Walking the {result['channel']} simulation (compliant path)")
                walk_interactive(api, result)

    heading("Employee entry points")
    for result in results:
        print(f"  {result['channel']:<9} {result['entry_url']}")

    heading("Done")
    print("  Open the console at the frontend URL and review Command Center, Campaigns and Risk Intelligence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
