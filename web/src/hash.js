/** Shareable view state in the URL hash: #v=lng,lat,zoom&m=metric&t=threshold. */

import { map } from "./map.js";
import { setMetric, setThreshold } from "./panel.js";
import { state } from "./state.js";
import { $ } from "./util.js";

export function applyHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  const view = (params.get("v") || "").split(",").map(Number);
  if (view.length === 3 && view.every(Number.isFinite)) map.jumpTo({ center: [view[0], view[1]], zoom: view[2] });
  const metric = params.get("m");
  if (metric && [...$("metric").options].some((o) => o.value === metric)) setMetric(metric);
  const threshold = Number(params.get("t"));
  if (threshold >= 1 && threshold <= 20) setThreshold(threshold);
}

export function syncHash() {
  let timer;
  const save = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const c = map.getCenter();
      history.replaceState(
        null,
        "",
        `#v=${c.lng.toFixed(4)},${c.lat.toFixed(4)},${map.getZoom().toFixed(2)}&m=${state.metric}&t=${state.threshold}`,
      );
    }, 300);
  };
  map.on("moveend", save);
  $("metric").addEventListener("change", save);
  $("thr").addEventListener("change", save);
}
