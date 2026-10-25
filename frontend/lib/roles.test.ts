import { describe, expect, it } from "vitest";

import type { SessionData } from "./client-api";
import { canManageContent, hasAnyRole, isAdministrator } from "./roles";

function session(roles: string[]): SessionData {
  return {
    access_token: "",
    token_type: "bearer",
    user: { id: "u1", email: "person@example.com", full_name: "Person", roles, organization_id: "o1" },
  };
}

describe("role helpers", () => {
  it("lets administrators and campaign managers manage content", () => {
    expect(canManageContent(session(["admin"]))).toBe(true);
    expect(canManageContent(session(["campaign_manager"]))).toBe(true);
    expect(canManageContent(session(["auditor"]))).toBe(false);
    expect(canManageContent(null)).toBe(false);
  });

  it("reserves administration for the admin role", () => {
    expect(isAdministrator(session(["admin"]))).toBe(true);
    expect(isAdministrator(session(["campaign_manager", "auditor"]))).toBe(false);
    expect(hasAnyRole(session(["risk_identity_viewer"]), ["admin", "auditor"])).toBe(false);
  });
});
