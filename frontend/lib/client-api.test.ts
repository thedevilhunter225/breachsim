import { describe, expect, it } from "vitest";

import { formatErrorDetail } from "./client-api";

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
