function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return atob(padded);
}

export function isJwtExpired(token: string, nowMs: number = Date.now()): boolean {
  try {
    const parts = token.split(".");
    if (parts.length !== 3 || !parts[1]) return true;
    const payload = JSON.parse(decodeBase64Url(parts[1])) as { exp?: unknown };
    return typeof payload.exp !== "number" || payload.exp * 1000 <= nowMs;
  } catch {
    return true;
  }
}
