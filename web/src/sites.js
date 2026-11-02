/** "Where to build next": precomputed candidate sites, validated with real drive-time areas. */

import { loadSites } from "./api.js";
import { cancelPending, clearPin } from "./analysis.js";
import { SITE_LABEL } from "./config.js";
import { setIsoline } from "./layers.js";
import { map, overlay } from "./map.js";
import { data, state } from "./state.js";
import { $, esc, formatInt } from "./util.js";

const tabs = () => document.querySelectorAll("#sites .tabs button");

export function renderSites() {
  tabs().forEach((button) => button.classList.toggle("on", button.dataset.cat === state.siteCategory));
  const active = Boolean(state.siteCategory && data.sites);
  $("sitecsv").hidden = !active;
  if (!active) {
    $("sitesum").textContent =
      "Pick a service: the map shows where one new facility would bring the most residents within a 15-minute drive.";
    $("sitelist").innerHTML = "";
    return;
  }
  const entry = data.sites.categories[state.siteCategory];
  const share = ((entry.union_gain / entry.unserved) * 100).toFixed(1);
  $("sitesum").innerHTML =
    `${entry.sites.length} new ${SITE_LABEL[state.siteCategory]} sites would bring <b>${formatInt(entry.union_gain)}</b> ` +
    `residents (${share}% of the ${formatInt(entry.unserved)} farther than ${data.sites.radius_km} km) within a 15-minute drive. ` +
    `The straight-line estimate agrees with road routing (median ratio ${entry.median_ratio.toFixed(2)}).`;
  $("sitelist").innerHTML = entry.sites
    .map(
      (site) =>
        `<li data-r="${site.rank}" class="${site.rank - 1 === state.siteIndex ? "on" : ""}"><b>${site.rank}</b>` +
        `<i>${esc(site.comune)} · ${esc(site.prov)}</i><em>+${formatInt(site.road_gain)}</em></li>`,
    )
    .join("");
}

export async function openSites(category) {
  if (state.siteCategory === category) {
    state.siteCategory = null;
    state.siteIndex = null;
    setIsoline(null);
    renderSites();
    return;
  }
  try {
    await loadSites();
  } catch (error) {
    $("sitesum").innerHTML = `<span class="warn">Could not load the sites (${esc(error.message)}).</span>`;
    return;
  }
  cancelPending();
  state.siteCategory = category;
  state.siteIndex = null;
  setIsoline(null);
  renderSites();
}

export function closeSites() {
  state.siteCategory = null;
  state.siteIndex = null;
  renderSites();
}

export function selectSite(index) {
  const site = data.sites.categories[state.siteCategory].sites[index];
  if (!site) return;
  cancelPending();
  clearPin();
  state.siteIndex = index;
  setIsoline(site.isoline);
  renderSites();
  map.flyTo({ center: [site.lon, site.lat], zoom: 9.6, duration: 1500, essential: true });
  $("detail").innerHTML =
    `<h3>Site ${site.rank}: ${esc(site.comune)} <small>${esc(site.prov)}</small></h3>` +
    `<p>A new ${SITE_LABEL[state.siteCategory]} here would bring <b>${formatInt(site.road_gain)}</b> residents who live farther than ` +
    `${data.sites.radius_km} km today within a <b>15-minute drive</b> (area from Amazon Location Service, in blue).</p>` +
    `<p class="hint">Straight-line estimate: ${formatInt(site.gain)} residents. This is an area-level recommendation; ` +
    "the exact spot needs a local survey.</p>";
}

/** If the click hit a site marker, select it and return true. */
export function pickSiteAt(event) {
  if (!state.siteCategory) return false;
  const hit = overlay.pickObject({ x: event.point.x, y: event.point.y, radius: 12, layerIds: ["sites"] });
  if (!hit?.object) return false;
  selectSite(hit.object.rank - 1);
  return true;
}

function downloadCsv() {
  const entry = data.sites.categories[state.siteCategory];
  const header = [
    "service",
    "rank",
    "comune",
    "province",
    "lon",
    "lat",
    "residents_gained_15min_drive",
    "residents_gained_straight_line",
  ];
  const rows = entry.sites.map((s) => [
    state.siteCategory,
    s.rank,
    s.comune,
    s.prov,
    s.lon,
    s.lat,
    s.road_gain,
    s.gain,
  ]);
  const csv = [header, ...rows].map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  link.download = `isolated-italy-sites-${state.siteCategory}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

export function initSites() {
  tabs().forEach((button) => {
    button.onclick = () => openSites(button.dataset.cat);
  });
  $("sitelist").onclick = (event) => {
    const item = event.target.closest("li");
    if (item) selectSite(Number(item.dataset.r) - 1);
  };
  $("sitecsv").onclick = downloadCsv;
  renderSites();
}
