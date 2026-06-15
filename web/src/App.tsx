import { useEffect, useState } from "react";
import Rail, { type Route } from "./components/Rail";
import { fetchToday } from "./api";
import { verdictTone } from "./lib/ds";
import type { VerdictStatus } from "./ds";
import Hoje from "./pages/Hoje";
import Metricas from "./pages/Metricas";
import Checkin from "./pages/Checkin";
import Tendencias from "./pages/Tendencias";
import Treinos from "./pages/Treinos";
import Plano from "./pages/Plano";

export default function App() {
  const [route, setRoute] = useState<Route>("hoje");
  const [verdict, setVerdict] = useState<VerdictStatus>("go");

  // veredito do dia só pra colorir a luz do rail; falha silenciosa.
  useEffect(() => {
    fetchToday()
      .then((t) => setVerdict(verdictTone(t.status)))
      .catch(() => {});
  }, []);

  return (
    <div className="rk-app">
      <Rail active={route} onNavigate={setRoute} verdict={verdict} />
      <main className="rk-main">
        {route === "hoje" && <Hoje onVerdict={setVerdict} />}
        {route === "metricas" && <Metricas />}
        {route === "checkin" && <Checkin />}
        {route === "tendencias" && <Tendencias />}
        {route === "treinos" && <Treinos />}
        {route === "plano" && <Plano />}
      </main>
    </div>
  );
}
