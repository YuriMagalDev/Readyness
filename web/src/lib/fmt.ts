// Formata valor de métrica. unidade === "time" → segundos em [h:]mm:ss.
export function fmtMetric(value: number | null, unidade: string): string {
  if (value === null || value === undefined) return "—";
  if (unidade === "time") {
    const secs = Math.round(value);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    if (m >= 60) {
      const h = Math.floor(m / 60);
      return `${h}:${String(m % 60).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
    return `${m}:${String(s).padStart(2, "0")}`;
  }
  const num = Number.isInteger(value) ? value : Math.round(value * 10) / 10;
  return `${num}${unidade}`;
}
