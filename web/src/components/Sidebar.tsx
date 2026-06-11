interface Props {
  page: string;
  onNavigate: (page: string) => void;
}

const ITEMS = [
  { id: "hoje", label: "☀ Hoje" },
  { id: "plano", label: "📅 Plano Semanal" },
  { id: "dados", label: "📊 Dados" },
];

export default function Sidebar({ page, onNavigate }: Props) {
  return (
    <nav className="sidebar">
      <div className="brand">⚡ Garmin Coach</div>
      {ITEMS.map((it) => (
        <button
          key={it.id}
          className={"nav-item" + (page === it.id ? " active" : "")}
          onClick={() => onNavigate(it.id)}
        >
          {it.label}
        </button>
      ))}
    </nav>
  );
}
