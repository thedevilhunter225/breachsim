import { describe, expect, it } from "vitest";

import { isJwtExpired } from "./security";

function tokenWithPayload(payload: Record<string, unknown>): string {
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `header.${encoded}.signature`;
}

describe("isJwtExpired", () => {
  it("accepts a token whose expiry is in the future", () => {
    expect(isJwtExpired(tokenWithPayload({ exp: 2_000 }), 1_000_000)).toBe(false);
  });

  it("rejects expired, missing-expiry, and malformed tokens", () => {
    expect(isJwtExpired(tokenWithPayload({ exp: 1_000 }), 1_000_000)).toBe(true);
    expect(isJwtExpired(tokenWithPayload({ sub: "user" }), 1_000_000)).toBe(true);
    expect(isJwtExpired("not-a-jwt", 1_000_000)).toBe(true);
    expect(isJwtExpired("header.@@@.signature", 1_000_000)).toBe(true);
  });
});
