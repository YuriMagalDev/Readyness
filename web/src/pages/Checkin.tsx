import { useEffect, useState } from "react";
import { fetchMetrics, postCheckin } from "../api";
import { Button, Freshness } from "../ds";
import { useLucide } from "../lib/useLucide";

const CHECKINS = [
  { key: "hidratacao", label: "Hidratação", icon: "droplet", low: "desidratado", high: "bem hidratado" },
  { key: "energia", label: "Energia", icon: "zap", low: "esgotado", high: "cheio de energia" },
  { key: "soreness", label: "Dor muscular", icon: "flame", low: "muito dolorido", high: "sem dor" },
  { key: "alimentacao", label: "Alimentação", icon: "utensils", low: "mal alimentado", high: "bem alimentado" },
] as const;

type Key = (typeof CHECKINS)[number]["key"];

function Scale({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <div className="rk-scale" role="radiogroup">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          role="radio"
          aria-checked={value === n}
          className={`rk-scale__dot ${value === n ? "is-on" : ""} ${value && n <= value ? "is-filled" : ""}`}
          onClick={() => onChange(n)}
        >
          {n}
        </button>
      ))}
    </div>
  );
}

/** Check-in — auto-avaliação manual 1–5 (source="manual" no modelo de dados).
 *  Pré-carrega os valores do dia de /api/metrics; salva via POST /api/checkin. */
export default function Checkin() {
  const [vals, setVals] = useState<Record<Key, number>>({
    hidratacao: 0,
    energia: 0,
    soreness: 0,
    alimentacao: 0,
  });
  const [salvo, setSalvo] = useState<Record<Key, boolean>>({
    hidratacao: false,
    energia: false,
    soreness: false,
    alimentacao: false,
  });
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState(false);

  useLucide([vals, ok]);

  useEffect(() => {
    fetchMetrics()
      .then((m) => {
        const idx = new Map<string, number>();
        const present = new Set<string>();
        Object.values(m.dominios).forEach((cells) =>
          cells.forEach((c) => {
            if (c.value != null) idx.set(c.key, c.value);
            if (c.source === "manual" && c.value != null) present.add(c.key);
          }),
        );
        setVals((s) => {
          const next = { ...s };
          (Object.keys(next) as Key[]).forEach((k) => {
            if (idx.has(k)) next[k] = idx.get(k)!;
          });
          return next;
        });
        setSalvo((s) => {
          const next = { ...s };
          (Object.keys(next) as Key[]).forEach((k) => (next[k] = present.has(k)));
          return next;
        });
      })
      .catch(() => {});
  }, []);

  const set = (k: Key, v: number) => {
    setVals((s) => ({ ...s, [k]: v }));
    setOk(false);
  };
  const done = Object.values(vals).filter(Boolean).length;

  async function salvar() {
    setSaving(true);
    setErro("");
    try {
      const payload: Record<string, number> = {};
      (Object.keys(vals) as Key[]).forEach((k) => {
        if (vals[k]) payload[k] = vals[k];
      });
      await postCheckin(payload);
      setOk(true);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rk-screen rk-screen--narrow">
      <header className="rk-head">
        <div>
          <h1 className="rk-title">Check-in de hoje</h1>
          <div className="rk-head__sub">
            <span className="rk-date">Como você se sente? Leva 20 segundos.</span>
          </div>
        </div>
      </header>

      {erro && (
        <div className="rk-banner rk-banner--erro">
          <i data-lucide="triangle-alert"></i>
          <span>{erro}</span>
        </div>
      )}

      <div className="rk-checkins">
        {CHECKINS.map((c) => (
          <div className="rk-checkin" key={c.key}>
            <div className="rk-checkin__head">
              <span className="rk-checkin__icon">
                <i data-lucide={c.icon}></i>
              </span>
              <span className="rk-checkin__label">{c.label}</span>
              <Freshness
                status={vals[c.key] ? "fresh" : "absent"}
                when={vals[c.key] ? (salvo[c.key] ? "registrado" : "agora") : "pendente"}
                showLabel={false}
              />
            </div>
            <Scale value={vals[c.key]} onChange={(v) => set(c.key, v)} />
            <div className="rk-checkin__scale-labels">
              <span>{c.low}</span>
              <span>{c.high}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="rk-checkin__foot">
        <span className="rk-checkin__count">
          {ok ? "Check-in salvo." : `${done} de 4 respondidos`}
        </span>
        <Button variant="primary" disabled={saving || done === 0} onClick={salvar}>
          <i data-lucide="check"></i> {saving ? "Salvando…" : "Salvar check-in"}
        </Button>
      </div>
    </div>
  );
}
