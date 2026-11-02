/** Small DOM and formatting helpers. */

export const $ = (id) => document.getElementById(id);

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escape text for safe insertion into innerHTML. */
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);

export const formatInt = (n) => Number(n).toLocaleString("en-US");

/** Compact count: 4 513 824 -> "4.5 M", 159 193 -> "159k". */
export function formatCompact(n) {
  return n >= 1e6 ? `${(n / 1e6).toFixed(1)} M` : `${Math.round(n / 1000)}k`;
}

export const isMobile = () => window.innerWidth < 700;
