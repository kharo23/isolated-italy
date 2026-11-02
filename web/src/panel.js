/** Side panel: headline, controls, ranking, search and footer. */

import { cancelPending, clearPin } from "./analysis.js";
import { ESSENTIAL, SERVICE_LABEL, THRESHOLD_STEPS } from "./config.js";
import { render, setIsoline } from "./layers.js";
import { map } from "./map.js";
import { data, state } from "./state.js";
import { $, esc, formatCompact, formatInt } from "./util.js";

export function renderSubtitle() {
  const millions = (data.headline.total / 1e6).toFixed(0);
  $("sub").innerHTML =
    `Where essential services are out of reach: ${millions}&nbsp;M residents (modelled), 164&nbsp;k places. ` +
    "Straight-line map; real road times on click.";
}

export function renderHeadline() {
  const h = data.headline;
  const percent = (n) => ((n / h.total) * 100).toFixed(1);
  const registerFar = h.pharm_both + h.pharm_only_overture_says_near;
  const overtureFar = h.pharm_both + h.pharm_only_register_says_near;
  const disagree = h.pharm_only_overture_says_near + h.pharm_only_register_says_near;
  $("headline").innerHTML =
    `<div class="big"><b>${formatCompact(h.pharm_both)}</b><span>residents live more than ${h.thr_km} km from a pharmacy in ` +
    `<u>both</u> open sources. Each source alone says about ${formatCompact(Math.round((registerFar + overtureFar) / 2 / 5000) * 5000)}: they disagree on ` +
    `${formatCompact(disagree)} people.</span></div>` +
    `<div class="row"><div><b>${formatCompact(h.far1)}</b><span>${percent(h.far1)}% over ${h.thr_km} km from at least one of five services</span></div>` +
    `<div><b>${formatCompact(h.far3)}</b><span>from three or more</span></div></div>` +
    '<p class="hint">Pharmacies: Ministry of Health register and Overture. Doctors and schools: Overture only, not validated, lower confidence.</p>';
}

/** Small islands are left out of the ranking: their nearest service is across the sea and ferries are not modelled. */
const isSmallIsland = (l) => Math.max(l.d_pharmacy, l.d_health, l.d_school) > 15 && l.n < 6000;

export function renderRanking() {
  const top = data.localities
    .filter((l) => l.n >= 2000 && !isSmallIsland(l))
    .sort((a, b) => b.iso3 - a.iso3 || b.n - a.n)
    .slice(0, 12);
  $("rank").innerHTML = top
    .map(
      (l) =>
        `<li data-i="${data.localities.indexOf(l)}"><b>${esc(l.name)}</b> <i>${esc(l.prov)}</i><em>${Math.round(l.iso3 * 100)}%</em></li>`,
    )
    .join("");
  $("rank").onclick = (event) => {
    const item = event.target.closest("li");
    if (item) flyToLocality(data.localities[Number(item.dataset.i)]);
  };
}

export function flyToLocality(locality) {
  cancelPending();
  setIsoline(null);
  clearPin();
  map.flyTo({ center: [locality.lon, locality.lat], zoom: 10.5, duration: 1800, essential: true });
  const rows = ESSENTIAL.map(
    (c) => `<tr><td>${SERVICE_LABEL[c]}</td><td>${(locality[`d_${c}`] ?? 0).toFixed(1)} km</td></tr>`,
  ).join("");
  $("detail").innerHTML =
    `<h3>${esc(locality.name)} <small>${esc(locality.prov)}</small></h3>` +
    `<p>${Math.round(locality.iso3 * 100)}% of its ${formatInt(locality.n)} residents live beyond ${data.headline.thr_km} km of three or more essential services.</p>` +
    `<table><tr><th></th><th>average straight-line</th></tr>${rows}</table>` +
    '<p class="hint">Click the map to measure real road times from any point.</p>';
}

export function initSearch() {
  $("comlist").innerHTML = data.localities
    .map((l) => `<option value="${esc(l.name)} (${esc(l.prov)})"></option>`)
    .join("");
  $("search").addEventListener("change", () => {
    const query = $("search").value.trim().toLowerCase();
    if (!query) return;
    const label = (l) => `${l.name} (${l.prov})`.toLowerCase();
    const found =
      data.localities.find((l) => label(l) === query) ||
      data.localities.find((l) => l.name.toLowerCase() === query) ||
      data.localities.find((l) => l.name.toLowerCase().includes(query) || l.prov.toLowerCase() === query);
    if (found) flyToLocality(found);
    else $("detail").innerHTML = `<p class="hint warn">No locality matches "${esc(query)}".</p>`;
  });
}

export function setThreshold(km) {
  const nearest = THRESHOLD_STEPS.reduce((a, b) => (Math.abs(b - km) < Math.abs(a - km) ? b : a));
  state.threshold = nearest;
  $("thr").value = String(THRESHOLD_STEPS.indexOf(nearest));
  $("thrv").textContent = String(nearest);
}

export function setMetric(metric) {
  state.metric = metric;
  $("metric").value = metric;
}

export function initControls() {
  $("metric").onchange = (event) => {
    state.metric = event.target.value;
    render();
  };
  $("thr").oninput = (event) => {
    setThreshold(THRESHOLD_STEPS[Number(event.target.value)]);
    render();
  };
  $("ext").onchange = (event) => {
    state.extrude = event.target.checked;
    map.easeTo({ pitch: state.extrude ? 50 : 0, duration: 500 });
    render();
  };
  $("toggle").onclick = () => document.body.classList.toggle("collapsed");
  $("dclose").onclick = () => {
    cancelPending();
    $("detail").innerHTML = "";
    setIsoline(null);
    clearPin();
  };
  new MutationObserver(() => {
    const visible = $("detail").innerHTML.trim() !== "";
    $("detailbox").hidden = !visible;
    document.body.classList.toggle("has-detail", visible);
  }).observe($("detail"), { childList: true, subtree: true });
}

export function renderFooter(lakehouse) {
  const link = (href, text) => `<a href="${href}" target="_blank" rel="noopener">${text}</a>`;
  let html =
    `Services: pharmacies from the ${link("https://www.dati.salute.gov.it/it/dataset/farmacie/", "Italian Ministry of Health open register")} ` +
    `(IODL 2.0, active entries); everything else from ${link("https://overturemaps.org", "Overture Maps")} release ${data.headline.release} ` +
    `(CDLA-Permissive-2.0 / ODbL) through the ${link("https://registry.opendata.aws/overture/", "Registry of Open Data on AWS")}. ` +
    `Residents: ${link("https://human-settlement.emergency.copernicus.eu/", "GHS-POP 2025")} (JRC, CC BY 4.0), a model built from ` +
    "censuses and spread over buildings, not a census count. Map colours use straight-line distance; the click analysis uses road " +
    "routing from Amazon Location Service. A gap can also be a hole in the source data. " +
    `${link("https://github.com/kharo23/isolated-italy", "Source code and method")}.`;
  if (lakehouse) {
    html +=
      `<br><b>Engine check:</b> the headline numbers are computed by Amazon Athena over an Apache Iceberg table on S3 ` +
      `(${lakehouse.data_files} data files, ${(lakehouse.bytes / 1e6).toFixed(0)} MB) and must equal the DuckDB result.`;
  }
  $("foot").innerHTML = html;
}
