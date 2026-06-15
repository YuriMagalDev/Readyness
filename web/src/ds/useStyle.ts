/** Injeta o CSS de um componente uma única vez no <head>. */
export function useStyle(id: string, css: string): void {
  if (typeof document !== "undefined" && !document.getElementById(id)) {
    const el = document.createElement("style");
    el.id = id;
    el.textContent = css;
    document.head.appendChild(el);
  }
}
