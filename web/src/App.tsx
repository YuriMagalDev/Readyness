import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Hoje from "./pages/Hoje";
import Tendencias from "./pages/Tendencias";
import Treinos from "./pages/Treinos";
import Plano from "./pages/Plano";

export default function App() {
  const [page, setPage] = useState("hoje");
  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={setPage} />
      <main className="main">
        {page === "hoje" && <Hoje />}
        {page === "tendencias" && <Tendencias />}
        {page === "treinos" && <Treinos />}
        {page === "plano" && <Plano />}
      </main>
    </div>
  );
}
