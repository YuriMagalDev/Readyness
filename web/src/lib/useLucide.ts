import { useEffect } from "react";

declare global {
  interface Window {
    lucide?: { createIcons: () => void };
  }
}

/** Re-renderiza os ícones Lucide (<i data-lucide="...">) após cada render.
 *  Lucide é carregado via CDN no index.html; pode ainda não ter chegado no
 *  primeiro paint, daí o retry curto. */
export function useLucide(dep?: unknown): void {
  useEffect(() => {
    if (window.lucide) {
      window.lucide.createIcons();
    } else {
      const id = setTimeout(() => window.lucide?.createIcons(), 200);
      return () => clearTimeout(id);
    }
  });
  void dep;
}
