import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Hoje from "./pages/Hoje";
import Plano from "./pages/Plano";
import Dados from "./pages/Dados";

export default function App() {
  const [page, setPage] = useState("hoje");
  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={setPage} />
      <main className="main">
        {page === "hoje" && <Hoje />}
        {page === "plano" && <Plano />}
        {page === "dados" && <Dados />}
      </main>
    </div>
  );
}
