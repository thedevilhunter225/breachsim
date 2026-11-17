import { describe, expect, it } from "vitest";

import { ApiError, formatErrorDetail, isMfaSetupRequired } from "./client-api";

describe("formatErrorDetail", () => {
  it("returns plain string details without JSON quotes", () => {
    expect(formatErrorDetail("Invalid credentials")).toBe("Invalid credentials");
  });

  it("turns FastAPI validation errors into field messages", () => {
    const detail = [
      { type: "string_too_short", loc: ["body", "password"], msg: "String should have at least 14 characters" },
      { type: "missing", loc: ["body", "full_name"], msg: "Field required" },
    ];
    expect(formatErrorDetail(detail)).toBe(
      "password: String should have at least 14 characters; full name: Field required",
    );
  });

  it("prefers a message field on object details", () => {
    expect(formatErrorDetail({ code: "policy_blocked", message: "Theme is not allowed" })).toBe("Theme is not allowed");
  });

  it("joins policy error lists", () => {
    expect(formatErrorDetail({ errors: ["Theme is not allowed.", "Prohibited word."] })).toBe(
      "Theme is not allowed. Prohibited word.",
    );
  });

  it("falls back to JSON for unknown shapes", () => {
    expect(formatErrorDetail({ code: 7 })).toBe('{"code":7}');
  });
});

describe("isMfaSetupRequired", () => {
  const setupDetail = { code: "mfa_setup_required", message: "MFA enrollment is required for this account" };

  it("recognises the sign-in refusal that asks for two-step setup", () => {
    expect(isMfaSetupRequired(new ApiError(setupDetail.message, 403, { detail: setupDetail }))).toBe(true);
  });

  it("ignores other refusals, including a wrong code or a plain 403", () => {
    expect(isMfaSetupRequired(new ApiError("A valid MFA code is required", 401, { detail: "A valid MFA code is required" }))).toBe(false);
    expect(isMfaSetupRequired(new ApiError("Insufficient permissions", 403, { detail: "Insufficient permissions" }))).toBe(false);
    expect(isMfaSetupRequired(new ApiError(setupDetail.message, 401, { detail: setupDetail }))).toBe(false);
    expect(isMfaSetupRequired(new ApiError("Forbidden", 403, null))).toBe(false);
    expect(isMfaSetupRequired(new Error("network"))).toBe(false);
  });
});
