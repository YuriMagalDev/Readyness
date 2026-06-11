export interface TodayMetrics {
  resting_hr_today: number;
  resting_hr_avg_7d: number;
  morning_battery_avg: number;
  sleep_debt_hours: number;
  run_sessions_7d: number;
}

export interface Today {
  status: "verde" | "amarelo" | "vermelho";
  motivo: string;
  recomendacao: string;
  metrics: TodayMetrics;
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
