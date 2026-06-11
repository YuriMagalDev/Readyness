import type { Today, Plan, Dados, Trends, ActivitySummary, ActivityDetail } from "./types";

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
