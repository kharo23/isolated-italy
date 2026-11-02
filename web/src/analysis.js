/** Click analysis: straight-line distances, road routes and the 15-minute drive area. */

import { fetchReach, loadServices } from "./api.js";
import { ROUTED, SERVICE_LABEL, SERVICES, ITALY_BOUNDS } from "./config.js";
import { countInGeometry, insideItaly, nearestPoint } from "./geo.js";
import { setIsoline } from "./layers.js";
import { Marker, map } from "./map.js";
import { data, state } from "./state.js";
import { $, esc, formatInt } from "./util.js";

const ERROR_MESSAGES = {
  no_road: "No drivable road near this point. Click closer to a road.",
  routing_unavailable: "Routing is temporarily unavailable.",
  daily_cap_reached: "The daily routing budget of this demo is used up. Try again tomorrow.",
};

/** Invalidate in-flight work so that stale responses are ignored. */
export const cancelPending = () => ++state.requestId;

export function clearPin() {
  state.pin?.remove();
}

function placePin(lon, lat) {
  state.pin ??= new Marker({ color: "#fde047" });
  state.pin.setLngLat([lon, lat]).addTo(map);
}

const showMessage = (html) => {
  $("detail").innerHTML = html;
};

function resultTable(nearest, reach) {
  const rows = SERVICES.map((category) => {
    const route = reach?.routes?.[category];
    const inside = reach?.isoline ? countInGeometry(data.services[category], reach.isoline) : null;
    const road = route ? `<b>${Math.round(route.minutes)} min</b> · ${route.km.toFixed(1)} km` : "n/a";
    return `<tr><td>${SERVICE_LABEL[category]}</td><td>${nearest[category].km.toFixed(1)} km</td><td>${road}</td><td>${inside ?? "n/a"}</td></tr>`;
  }).join("");
  return `<table class="reach"><tr><th></th><th>Crow</th><th>Road to crow-nearest</th><th>In 15 min</th></tr>${rows}</table>`;
}

/**
 * Analyse a point. `cell` is the hexagon under the pointer, if any.
 * The road time shown is to the service that is nearest in a straight line, which bounds the nearest by road.
 */
export async function analyse(lon, lat, cell) {
  const id = cancelPending();
  placePin(lon, lat);
  setIsoline(null);
  showMessage('<p class="hint">Asking Amazon Location Service for real road times…</p>');
  try {
    await loadServices();
  } catch (error) {
    if (id === state.requestId)
      showMessage(`<p class="hint warn">Could not load the service points (${esc(error.message)}). Please retry.</p>`);
    return;
  }
  if (id !== state.requestId) return;

  const nearest = Object.fromEntries(SERVICES.map((c) => [c, nearestPoint(data.services[c], lon, lat)]));
  if (nearest.pharmacy.km > 60 && nearest.grocery.km > 40) {
    showMessage('<p class="hint warn">Outside the data area. Click on Italian territory.</p>');
    return;
  }

  let reach = null;
  let error = "";
  try {
    reach = await fetchReach({ lon, lat }, Object.fromEntries(ROUTED.map((c) => [c, nearest[c]])));
  } catch (e) {
    error = String(e.message || e);
  }
  if (id !== state.requestId) return;

  setIsoline(reach?.isoline);
  const title = cell ? `${formatInt(cell.n)} residents around here` : "This point";
  const footer = reach
    ? '<p class="hint">Road times (pharmacy, doctor, school) and the 15-minute drive area come from Amazon Location Service (Routes API).</p>'
    : `<p class="hint warn">${ERROR_MESSAGES[error] || "Live routing unavailable."} Showing straight-line distances only.</p>`;
  showMessage(`<h3>${title}</h3>${resultTable(nearest, reach)}${footer}`);
}

export function handleMapClick(event, { onSiteHit }) {
  const { lng, lat } = event.lngLat;
  if (!insideItaly(lng, lat, ITALY_BOUNDS)) {
    showMessage('<p class="hint warn">Click inside Italy: the data covers Italian territory only.</p>');
    return;
  }
  if (onSiteHit?.(event)) return;
  analyse(lng, lat, state.hovered);
}
