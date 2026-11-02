/** Runs the guided tour. */

import { analyse } from "./analysis.js";
import { DEFAULT_THRESHOLD_KM } from "./config.js";
import { render } from "./layers.js";
import { map } from "./map.js";
import { setMetric, setThreshold } from "./panel.js";
import { openSites, selectSite } from "./sites.js";
import { state } from "./state.js";
import { TOUR } from "./tour.js";
import { $ } from "./util.js";

const START_LABEL = "Take the 60-second tour";
const STOP_LABEL = "Stop the tour";

let running = false;
let runId = 0;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const isTouring = () => running;

function finish() {
  running = false;
  $("tour").textContent = START_LABEL;
  $("caption").style.opacity = 0;
}

export function stopTour() {
  if (!running) return;
  runId++;
  map.stop();
  finish();
}

async function run() {
  const id = ++runId;
  const cancelled = () => id !== runId;
  running = true;
  $("tour").textContent = STOP_LABEL;
  setThreshold(DEFAULT_THRESHOLD_KM);
  state.extrude = false;
  $("ext").checked = false;
  if (state.siteCategory) await openSites(state.siteCategory); // close an open site view

  for (const stop of TOUR) {
    if (cancelled()) return;
    $("caption").innerHTML = `<b>${stop.title}</b><span>${stop.text}</span>`;
    $("caption").style.opacity = 1;
    if (stop.metric) {
      setMetric(stop.metric);
      render();
    }
    map.flyTo({ center: stop.center, zoom: stop.zoom, pitch: stop.pitch || 0, duration: 3200, essential: true });
    await sleep(stop.hold || 6500);
    if (cancelled()) return;
    if (stop.sites) {
      await openSites(stop.sites);
      if (cancelled()) return;
      selectSite(stop.site || 0);
      await sleep(5500);
      if (cancelled()) return;
    }
    if (stop.click) {
      await analyse(stop.center[0], stop.center[1], null);
      if (cancelled()) return;
      await sleep(5000);
    }
  }
  if (!cancelled()) finish();
}

export function initTour() {
  $("tour").onclick = () => (running ? stopTour() : run());
}
