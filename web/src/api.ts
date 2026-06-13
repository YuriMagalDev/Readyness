import type { Today, Plan, Dados, Trends, ActivitySummary, ActivityDetail, PlanStatus, MetricsPayload, Analysis } from "./types";

async function get<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}

export const fetchToday = () => get<Today>("/api/today");
export const fetchDados = () => get<Dados>("/api/data");

export async function generatePlan(): Promise<Plan> {
  const resp = await fetch("/api/plan", { method: "POST" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}

export const fetchPlanStatus = () => get<PlanStatus>("/api/plan");

export const fetchTrends = (period = 30) => get<Trends>(`/api/trends?period=${period}`);
export const fetchActivities = (period = 30) =>
  get<ActivitySummary[]>(`/api/activities?period=${period}`);
export const fetchActivity = (id: number) => get<ActivityDetail>(`/api/activity/${id}`);

export async function postSync(): Promise<{ ok: boolean }> {
  const resp = await fetch("/api/sync", { method: "POST" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}

export async function syncGarmin(): Promise<{ ok: boolean }> {
  const resp = await fetch("/api/sync/garmin", { method: "POST" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}

export async function regenerateInsights(
  page: "hoje" | "trends",
  period?: number,
): Promise<unknown> {
  const resp = await fetch("/api/sync/insights", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ page, period }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}

export const fetchMetrics = (date?: string) =>
  get<MetricsPayload>(`/api/metrics${date ? `?date=${date}` : ""}`);

export const fetchAnalysis = (date?: string) =>
  get<Analysis>(`/api/analysis${date ? `?date=${date}` : ""}`);

export async function regenerateAnalysis(date?: string): Promise<Analysis> {
  const resp = await fetch("/api/analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}

export async function postCheckin(payload: Record<string, number>): Promise<{ ok: boolean }> {
  const resp = await fetch("/api/checkin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}
