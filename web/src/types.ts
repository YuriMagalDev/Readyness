export interface TodayMetrics {
  resting_hr_today: number;
  resting_hr_avg_7d: number;
  morning_battery_avg: number;
  sleep_debt_hours: number;
  run_sessions_7d: number;
}

export interface Param {
  label: string;
  icon: string;
  valor: number;
  unidade: string;
  valor_fmt?: string;
  delta: number | null;
  delta_fmt?: string;
  direcao: "subiu" | "desceu" | "estável";
  bom: boolean | null;
  data: string;
  data_anterior: string | null;
}

export interface Today {
  status: "verde" | "amarelo" | "vermelho";
  motivo: string;
  recomendacao: string;
  metrics: TodayMetrics;
  daily_insight?: string;
  parametros?: Param[];
}

export interface PlanItem {
  dia: string;
  descricao: string;
  duracao: number;
  intensidade: string;
}

export interface Plan {
  corrida: PlanItem[];
  musculacao: PlanItem[];
}

export interface PlanSessionStatus {
  dia: string;
  descricao: string;
  duracao: number;
  intensidade: string;
  date: string;
  status: "feito" | "pendente" | "furou";
}

export interface PlanMatch {
  corrida: PlanSessionStatus[];
  musculacao: PlanSessionStatus[];
}

export interface PlanStatus {
  plan: Plan | null;
  match: PlanMatch | null;
  week_start: string;
  created_at?: string;
}

export interface SeriePoint {
  data: string;
  valor: number | null;
}

export interface Trend {
  delta: number;
  label: string;
}

export interface Atividade {
  data: string;
  nome: string;
  tipo: string;
  is_strength: boolean;
  duracao: number;
}

export interface Dados {
  fc_series: SeriePoint[];
  battery_series: SeriePoint[];
  sleep_series: SeriePoint[];
  fc_trend: Trend;
  battery_trend: Trend;
  atividades: Atividade[];
}

export interface TrendInfo {
  slope: number;
  direction: "subindo" | "descendo" | "estável";
}

export interface MetricTrend {
  series: SeriePoint[];
  trend: TrendInfo;
}

export interface Trends {
  period: number;
  metrics: Record<string, MetricTrend>;
  insights: string[];
}

export interface ActivitySummary {
  activity_id: number;
  date: string;
  name: string;
  type: string;
  is_strength: number;
  distance_m: number | null;
  duration_min: number | null;
  pace_min_km: number | null;
  avg_hr: number | null;
}

export interface Split {
  distance_m: number | null;
  duration_s: number | null;
  pace_min_km: number | null;
  avg_hr: number | null;
  cadence: number | null;
}

export interface ActivityDetail {
  activity: ActivitySummary;
  splits: Split[];
  insight: string;
}

export type MetricStatus = "fresco" | "velho" | "ausente" | "estimado";

export interface MetricCell {
  key: string;
  label: string;
  value: number | null;
  unidade: string;
  measured_at: string | null;
  status: MetricStatus;
  source: string;
}

export interface MetricsPayload {
  date: string;
  dominios: Record<string, MetricCell[]>;
}

export interface InsightSource {
  key: string;
  label: string;
  valor: number | null;
  unidade: string;
  status: MetricStatus;
}

export interface Insight {
  texto: string;
  metricas_usadas: InsightSource[];
}

export interface Analysis {
  date: string;
  veredito: { semaforo: "verde" | "amarelo" | "vermelho"; motivo: string; recomendacao: string };
  insights: Insight[];
}
