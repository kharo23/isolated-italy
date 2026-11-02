/** Entry point. */

import "./style.css";
import { analyse, handleMapClick } from "./analysis.js";
import { fetchJson, loadCoreData } from "./api.js";
import { applyHash, syncHash } from "./hash.js";
import { render } from "./layers.js";
import { map, showItaly } from "./map.js";
import { initControls, initSearch, renderFooter, renderHeadline, renderRanking, renderSubtitle } from "./panel.js";
import { initPlaces } from "./places.js";
import { initSites, openSites, pickSiteAt, selectSite } from "./sites.js";
import { state } from "./state.js";
import { initTour, isTouring } from "./tourRunner.js";
import { $, esc, isMobile } from "./util.js";

async function start() {
  initControls();
  initSites();
  initPlaces();
  initTour();
  if (isMobile()) document.body.classList.add("collapsed");
  map.on("click", (event) => {
    if (!isTouring()) handleMapClick(event, { onSiteHit: pickSiteAt });
  });
  if (!location.hash.includes("v=")) showItaly(false);
  applyHash();
  syncHash();

  $("headline").innerHTML = '<p class="hint">Loading the map…</p>';
  try {
    await loadCoreData();
  } catch (error) {
    $("headline").innerHTML =
      `<p class="hint warn">Could not load the data (${esc(error.message)}). Please reload.</p>`;
    return;
  }
  renderSubtitle();
  renderHeadline();
  renderRanking();
  initSearch();
  render();
  const lakehouse = await fetchJson("/data/lakehouse.json").catch(() => null);
  renderFooter(lakehouse);
}

// Hook for end-to-end tests and scripted recordings: enabled with ?e2e in the URL.
if (new URLSearchParams(location.search).has("e2e")) {
  window.__app = { map, state, analyse, openSites, selectSite };
}

start();
