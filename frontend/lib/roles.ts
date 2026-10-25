import type { SessionData } from "@/lib/client-api";

/**
 * UI mirror of the API's role checks. The API enforces every rule; these helpers only
 * hide controls a read-only role (auditor, named-report viewer) could never use.
 */
export function hasAnyRole(session: SessionData | null | undefined, roles: readonly string[]): boolean {
  return Boolean(session?.user.roles.some((role) => roles.includes(role)));
}

/** Create and edit employees, scenarios and campaigns. */
export function canManageContent(session: SessionData | null | undefined): boolean {
  return hasAnyRole(session, ["admin", "campaign_manager"]);
}

/** Approvals, deletions and workspace settings. */
export function isAdministrator(session: SessionData | null | undefined): boolean {
  return hasAnyRole(session, ["admin"]);
}
