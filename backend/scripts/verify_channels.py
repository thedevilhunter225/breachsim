"""End-to-end capability check across all five simulation channels.

Exercises every channel through the public API exactly as the console does — no
guardrail is bypassed — and reports what genuinely works versus what needs an
external provider. Use this before a demo or a submission to confirm the platform
is in a working state.

Usage::

    python scripts/verify_channels.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

API = "http://127.0.0.1:8000/api/v1"
APP = "http://localhost:3000"

PASS, FAIL, WARN = "PASS", "FAIL", "NEEDS PROVIDER"
results: list[tuple[str, str, str]] = []


def record(area: str, status: str, detail: str) -> None:
    results.append((area, status, detail))
    marker = {"PASS": "[ok]", "FAIL": "[XX]", "NEEDS PROVIDER": "[--]"}[status]
    print(f"  {marker} {area}: {detail}")


class Client:
    def __init__(self) -> None:
        self.http = httpx.Client(timeout=90.0)
        self.tokens: dict[str, str] = {}

    def login(self) -> None:
        for role, (email, pw) in {
            "admin": ("admin@breachsim-lab.com", "Admin123!"),
            "reviewer": ("reviewer@breachsim-lab.com", "Reviewer123!"),
            "manager": ("manager@breachsim-lab.com", "Manager123!"),
        }.items():
            r = self.http.post(
                f"{API}/auth/login",
                json={"email": email, "password": pw},
                headers={"X-BreachSim-API-Client": "bearer"},
            )
            r.raise_for_status()
            self.tokens[role] = r.json()["access_token"]

    def call(self, method: str, path: str, role: str = "admin", **kw) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.tokens[role]}"}
        return self.http.request(method, f"{API}{path}", headers=headers, **kw)

    def public(self, method: str, path: str, **kw) -> httpx.Response:
        return self.http.request(method, f"{API}{path}", **kw)


def ensure_scope(c: Client) -> None:
    policy = c.call("GET", "/policies/current").json()
    themes = ["invoice/payment approval", "policy update", "qr verification", "password reset",
              "executive approval request"]
    changed = False
    for ch in ["email", "sms", "qr", "vishing", "deepfake"]:
        if ch not in policy["allowed_delivery_channels"]:
            policy["allowed_delivery_channels"].append(ch)
            changed = True
    for t in themes:
        if t not in policy["allowed_themes"]:
            policy["allowed_themes"].append(t)
            changed = True
    if changed:
        policy.pop("id", None)
        policy.pop("organization_id", None)
        c.call("PUT", "/policies/current", json=policy)

    settings = c.call("GET", "/integrations/impersonation").json()
    if not settings["impersonation_enabled"]:
        c.call("PUT", "/integrations/impersonation", json={
            "impersonation_enabled": True,
            "impersonation_disclosure_text": settings["impersonation_disclosure_text"],
            "voice_provider_enabled": False,
            "voice_provider_mode": "simulator",
        })


def ensure_personas(c: Client) -> dict[str, str]:
    existing = {p["display_name"]: p for p in c.call("GET", "/personas").json()}
    out: dict[str, str] = {}
    specs = {
        "voice": {"display_name": "Verify Voice Persona", "role_title": "Service Desk Lead",
                  "modality": "voice_note"},
        "video": {"display_name": "Verify Video Persona", "role_title": "Group Finance Director",
                  "modality": "video_message"},
    }
    for key, spec in specs.items():
        found = existing.get(spec["display_name"])
        if found and found["usable"]:
            out[key] = found["id"]
            continue
        payload = {**spec, "is_real_person": False, "relationship_to_targets": "internal",
                   "consent_expires_at": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()}
        created = c.call("POST", "/personas", role="admin", json=payload).json()
        approved = c.call("POST", f"/personas/{created['id']}/approve", role="reviewer").json()
        out[key] = approved["id"]
    return out


def run_channel(c: Client, *, channel: str, theme: str, persona_id: str | None, employee: dict) -> dict | None:
    body = {"employee_id": employee["id"], "channel": channel, "theme": theme,
            "difficulty_level": "high"}
    if persona_id:
        body["persona_id"] = persona_id

    r = c.call("POST", "/scenarios/generate", role="manager", json=body)
    if r.status_code != 201:
        record(f"{channel} scenario", FAIL, f"generation returned {r.status_code}: {r.text[:150]}")
        return None
    scenario = r.json()
    version = scenario.get("latest_version") or {}
    payload = version.get("channel_payload") or {}

    if channel in ("vishing", "deepfake"):
        steps = len(payload.get("script") or [])
        if steps == 0:
            record(f"{channel} script", FAIL, "no branching script generated")
            return None
        record(f"{channel} script", PASS, f"{steps} decision points generated")

    c.call("POST", f"/scenarios/{scenario['id']}/approve", role="admin")
    cid = c.call("POST", "/campaigns", role="manager", json={
        "name": f"Verify {channel}", "channel": channel,
        "target_employee_ids": [employee["id"]], "scenario_ids": [scenario["id"]],
        "requires_second_approval": False}).json()["id"]
    c.call("POST", f"/campaigns/{cid}/request-approval", role="manager")
    c.call("POST", f"/campaigns/{cid}/approve", role="admin")

    r = c.call("POST", f"/campaigns/{cid}/deliver", role="manager")
    if r.status_code != 200:
        record(f"{channel} delivery", FAIL, f"{r.status_code}: {r.text[:150]}")
        return None
    attempt = r.json()[0]
    pp = attempt["preview_payload"]
    entry = pp.get("entry_url") or pp.get("preview_url")

    if attempt["status"] == "delivered":
        record(f"{channel} delivery", PASS, "sent via configured provider")
    elif attempt["status"] == "sandboxed" and pp.get("sandbox_reason"):
        record(f"{channel} delivery", WARN,
               "ran as sandbox preview - no outbound provider enabled (pipeline itself works)")
    elif attempt["status"] == "sandboxed":
        record(f"{channel} delivery", PASS, "in-platform session activated (nothing sent by design)")
    else:
        record(f"{channel} delivery", FAIL, f"status={attempt['status']} error={pp.get('error')}")

    return {"channel": channel, "entry": entry, "payload": pp, "campaign_id": cid}


def walk_interactive(c: Client, res: dict) -> None:
    token = res["entry"].rstrip("/").rsplit("/", 1)[-1]
    channel = res["channel"]

    r = c.public("GET", f"/public/simulation/{token}")
    if r.status_code != 200:
        record(f"{channel} simulator", FAIL, f"load returned {r.status_code}")
        return
    state = r.json()
    step = state.get("current_step")
    if not step:
        record(f"{channel} simulator", FAIL, "no current step returned")
        return

    leaked = [k for opt in step["options"] for k in ("risk_weight", "safe", "event_type") if k in opt]
    record(f"{channel} answer-key safety", FAIL if leaked else PASS,
           "safe answer leaked to client!" if leaked else "options carry no answer key")

    # Remember the first step with one of *its own* valid options, so the replay check
    # below exercises duplicate detection rather than option validation.
    first_step_key = step["key"]
    first_step_choice = step["options"][0]["key"]

    guard, complied = 0, False
    while step and guard < 8:
        guard += 1
        choice = step["options"][0]["key"]
        rr = c.public("POST", f"/public/simulation/{token}/respond",
                      json={"step_key": step["key"], "response_key": choice, "elapsed_ms": 2500})
        if rr.status_code != 200:
            record(f"{channel} simulator", FAIL, f"respond returned {rr.status_code}")
            return
        out = rr.json()
        if out.get("assignment_id"):
            complied = True
        if out["finished"] or out["terminal"]:
            break
        step = out.get("next_step")

    replay = c.public("POST", f"/public/simulation/{token}/respond",
                      json={"step_key": first_step_key, "response_key": first_step_choice})
    record(f"{channel} replay protection", PASS if replay.status_code == 409 else FAIL,
           "duplicate step rejected (409)" if replay.status_code == 409
           else f"expected 409, got {replay.status_code}")

    summary = c.public("POST", f"/public/simulation/{token}/complete").json()
    record(f"{channel} debrief", PASS,
           f"outcome={summary['outcome']} steps={summary['steps_taken']} risk={summary['current_risk_score']}")
    record(f"{channel} remediation", PASS if complied else WARN,
           "training auto-assigned on compliance" if complied else "no compliance on this path")


def main() -> int:
    c = Client()
    try:
        c.login()
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach API at {API}: {exc}")
        return 1

    print("\nBreachSim channel verification\n" + "=" * 60)
    ensure_scope(c)
    personas = ensure_personas(c)
    employee = c.call("GET", "/employees", role="manager").json()[0]
    print(f"Target: {employee['full_name']}\n")

    plan = [
        ("email", "invoice/payment approval", None),
        ("sms", "policy update", None),
        ("qr", "qr verification", None),
        ("vishing", "password reset", personas["voice"]),
        ("deepfake", "executive approval request", personas["video"]),
    ]

    outcomes = []
    for channel, theme, persona_id in plan:
        print(f"-- {channel} --")
        res = run_channel(c, channel=channel, theme=theme, persona_id=persona_id, employee=employee)
        if res:
            outcomes.append(res)
            if channel in ("vishing", "deepfake"):
                walk_interactive(c, res)
        print()

    # Reporting works off whatever ran above.
    if outcomes:
        cid = outcomes[-1]["campaign_id"]
        for fmt in ("html", "csv"):
            r = c.call("GET", f"/reports/campaign/{cid}/download?format={fmt}")
            record(f"report {fmt}", PASS if r.status_code == 200 else FAIL,
                   f"{len(r.content)} bytes" if r.status_code == 200 else f"HTTP {r.status_code}")

    print("\n" + "=" * 60)
    failed = [r for r in results if r[1] == FAIL]
    needs = [r for r in results if r[1] == WARN]
    print(f"{len(results) - len(failed) - len(needs)} working, {len(needs)} need a provider, {len(failed)} failing")
    if needs:
        print("\nNeeds an external provider (optional):")
        for area, _, detail in needs:
            print(f"  - {area}: {detail}")
    if failed:
        print("\nFailing:")
        for area, _, detail in failed:
            print(f"  - {area}: {detail}")

    print("\nEmployee entry points:")
    for res in outcomes:
        print(f"  {res['channel']:<9} {res['entry']}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
