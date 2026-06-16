/** Tema claro/escuro. Persiste em localStorage; aplica via data-theme no <html>.
 *  Default = claro (a identidade "warm paper" é clara); o escuro é o modo noite. */
export type Theme = "light" | "dark";

const KEY = "rk-theme";

export function currentTheme(): Theme {
  const t = document.documentElement.dataset.theme;
  return t === "dark" ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  if (theme === "dark") {
    document.documentElement.dataset.theme = "dark";
  } else {
    delete document.documentElement.dataset.theme;
  }
}

/** Lê a preferência salva e aplica. Chamado uma vez antes do render (evita flash). */
export function initTheme(): void {
  let stored: string | null = null;
  try {
    stored = localStorage.getItem(KEY);
  } catch {
    /* localStorage indisponível → fica no claro */
  }
  applyTheme(stored === "dark" ? "dark" : "light");
}

export function toggleTheme(): Theme {
  const next: Theme = currentTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  try {
    localStorage.setItem(KEY, next);
  } catch {
    /* ignora */
  }
  return next;
}
