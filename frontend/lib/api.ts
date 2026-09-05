import {
  demoAuditLogs,
  demoCampaigns,
  demoDashboard,
  demoDeliveryAttempts,
  demoEmployees,
  demoPolicy,
  demoScenarios,
} from "@/lib/demo-data";

const API_BASE =
  process.env.SERVER_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000/api/v1";
const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

async function fetchJSON<T>(path: string, fallback: T, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
    if (!response.ok && DEMO_MODE) {
      return fallback;
    }
    if (!response.ok) throw new Error(`BreachSim API request failed (${response.status})`);
    return (await response.json()) as T;
  } catch (error) {
    if (DEMO_MODE) return fallback;
    throw error;
  }
}

export function getDashboard() {
  return fetchJSON("/analytics/dashboard", demoDashboard);
}

export function getEmployees() {
  return fetchJSON("/employees", demoEmployees);
}

export function getPolicy() {
  return fetchJSON("/policies/current", demoPolicy);
}

export function getScenarios() {
  return fetchJSON("/scenarios", demoScenarios);
}

export function getCampaigns() {
  return fetchJSON("/campaigns", demoCampaigns);
}

export function getDeliveryAttempts() {
  return fetchJSON("/delivery-attempts", demoDeliveryAttempts);
}

export function getAuditLogs() {
  return fetchJSON("/audit-logs", demoAuditLogs);
}

export async function getTrainingToken(token: string) {
  return fetchJSON(`/public/training/${token}`, {
    token,
    landing_type: "email",
    training_banner: "Training simulation. No real credentials are stored.",
  });
}
