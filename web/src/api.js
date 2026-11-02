/** Network access: static data files and the reach API. */

import { API_BASE, SERVICES } from "./config.js";
import { data } from "./state.js";

export async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

/** Load the columnar display cells and expand them to one object per hexagon. */
export async function loadCoreData() {
  const [columns, localities, headline] = await Promise.all([
    fetchJson("/data/cells7.json"),
    fetchJson("/data/comuni.json"),
    fetchJson("/data/headline.json"),
  ]);
  const keys = Object.keys(columns);
  data.cells = columns.h.map((_, i) => Object.fromEntries(keys.map((k) => [k, columns[k][i]])));
  data.localities = localities;
  data.headline = headline;
}

/** Load the service point files on first use. */
export async function loadServices() {
  await Promise.all(
    SERVICES.filter((c) => !data.services[c]).map(async (category) => {
      const response = await fetch(`/data/svc_${category}.bin`);
      if (!response.ok) throw new Error(`svc_${category}: ${response.status}`);
      data.services[category] = new Float32Array(await response.arrayBuffer());
    }),
  );
}

export async function loadSites() {
  if (!data.sites) data.sites = await fetchJson("/data/sites.json");
  return data.sites;
}

/**
 * Ask the reach API for the 15-minute drive area around a point and road routes to the given destinations.
 * @param {{lon: number, lat: number}} origin
 * @param {Record<string, {lon: number, lat: number}>} destinations keyed by service category
 */
export async function fetchReach(origin, destinations) {
  const params = new URLSearchParams({ lon: origin.lon.toFixed(5), lat: origin.lat.toFixed(5), min: "15" });
  for (const [category, d] of Object.entries(destinations))
    params.set(category, `${d.lon.toFixed(5)},${d.lat.toFixed(5)}`);
  const response = await fetch(`${API_BASE}/api/reach?${params}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || String(response.status));
  }
  return response.json();
}
