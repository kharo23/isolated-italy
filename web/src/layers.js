/** deck.gl layers, colour scale, legend and tooltip. */

import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { GeoJsonLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { RAMP, SERVICE_LABEL, SERVICES } from "./config.js";
import { map, overlay } from "./map.js";
import { data, state } from "./state.js";
import { $, formatInt } from "./util.js";

/** Cells fade with zoom so the basemap stays readable up close. */
const zoomOpacity = () => (map.getZoom() >= 9 ? 0.45 : map.getZoom() >= 7.5 ? 0.7 : 1);

/** Mean number of out-of-reach services per resident, same definition as the headline. */
function cellValue(cell) {
  if (state.metric === "count") return Math.round(cell[`nf_${state.threshold}`] ?? 0);
  return cell[`d_${state.metric}`] ?? 0;
}

export function cellColor(cell) {
  const opacity = zoomOpacity();
  if (state.metric === "conflict") {
    const step = Math.round(Math.min((cell.cf ?? 0) * 2, 1) * 5);
    return [...RAMP[step], (step === 0 ? 60 : 215) * opacity];
  }
  const value = cellValue(cell);
  if (state.metric === "count") {
    return [...RAMP[Math.min(value, 5)], (value === 0 ? 70 : 215) * opacity];
  }
  const near = value <= state.threshold;
  const band = Math.min(Math.floor(Math.min(value / (state.threshold * 3), 1) * 4) + 1, 5);
  return [...RAMP[near ? 0 : band], (near ? 70 : 215) * opacity];
}

function swatch([r, g, b], label) {
  return `<span><i style="background:rgb(${r},${g},${b})"></i>${label}</span>`;
}

function renderLegend() {
  const t = state.threshold;
  let html;
  if (state.metric === "conflict") {
    const steps = [
      [0, "none"],
      [1, "10% or more"],
      [3, "30% or more"],
      [5, "50% or more"],
    ];
    html =
      "<b>Residents whose pharmacy access differs between the Ministry register and Overture</b>" +
      steps.map(([k, label]) => swatch(RAMP[k], label)).join("");
  } else if (state.metric === "count") {
    html =
      `<b>Essential services out of reach (more than ${t} km)</b>` +
      [0, 1, 2, 3, 4, 5].map((k) => swatch(RAMP[k], k === 0 ? "none" : String(k))).join("");
  } else {
    const mid = Math.trunc(t * 1.75);
    const high = Math.trunc(t * 2.5);
    html =
      `<b>Distance to ${SERVICE_LABEL[state.metric].toLowerCase()}</b>` +
      swatch(RAMP[0], `up to ${t} km`) +
      swatch(RAMP[1], `${t}-${mid}`) +
      swatch(RAMP[3], `${mid}-${high}`) +
      swatch(RAMP[5], `over ${high} km`);
  }
  $("legend").innerHTML = html;
}

function showTooltip(info) {
  let element = $("tip");
  if (!element) {
    element = document.createElement("div");
    element.id = "tip";
    document.body.appendChild(element);
  }
  const cell = info.object;
  if (!cell) {
    element.style.display = "none";
    return;
  }
  element.style.display = "block";
  element.style.left = `${info.x + 14}px`;
  element.style.top = `${info.y + 14}px`;
  element.innerHTML =
    `<b>${formatInt(cell.n)} residents</b>` +
    SERVICES.map((k) => `<div>${SERVICE_LABEL[k]}: ${cell[`d_${k}`]} km</div>`).join("") +
    `<div class="note">Pharmacy sources disagree for ${Math.round((cell.cf ?? 0) * 100)}% of residents</div>`;
}

function siteLayers() {
  const sites = data.sites.categories[state.siteCategory].sites;
  return [
    new ScatterplotLayer({
      id: "sites",
      data: sites,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 11,
      radiusUnits: "pixels",
      getFillColor: (d) => (d.rank - 1 === state.siteIndex ? [253, 224, 71, 255] : [56, 189, 248, 235]),
      getLineColor: [11, 18, 32, 255],
      stroked: true,
      lineWidthMinPixels: 2,
      pickable: true,
      updateTriggers: { getFillColor: [state.siteIndex] },
    }),
    new TextLayer({
      id: "site-ranks",
      data: sites,
      getPosition: (d) => [d.lon, d.lat],
      getText: (d) => String(d.rank),
      getSize: 12,
      getColor: [11, 18, 32, 255],
      fontWeight: 700,
      pickable: false,
    }),
  ];
}

/** Re-render all map layers from the current state. */
export function render() {
  renderLegend();
  const layers = [
    new H3HexagonLayer({
      id: "cells",
      data: data.cells,
      getHexagon: (d) => d.h,
      getFillColor: cellColor,
      filled: true,
      stroked: false,
      extruded: state.extrude,
      getElevation: (d) => (state.extrude ? Math.sqrt(d.n) * 18 : 0),
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 90],
      coverage: 0.96,
      updateTriggers: {
        getFillColor: [state.metric, state.threshold, state.zoomBand],
        getElevation: [state.extrude],
      },
      onHover: (info) => {
        state.hovered = info.object || null;
        showTooltip(info);
      },
    }),
  ];
  if (state.isoline) {
    layers.push(
      new GeoJsonLayer({
        id: "isoline",
        data: { type: "Feature", geometry: state.isoline, properties: {} },
        filled: true,
        stroked: true,
        getFillColor: [56, 189, 248, 70],
        getLineColor: [253, 224, 71, 255],
        getLineWidth: 3,
        lineWidthUnits: "pixels",
        pickable: false,
      }),
    );
  }
  if (state.siteCategory && data.sites) layers.push(...siteLayers());
  overlay.setProps({ layers });
}

export function setIsoline(geometry) {
  state.isoline = geometry || null;
  render();
}

map.on("zoomend", () => {
  const band = map.getZoom() >= 9 ? 2 : map.getZoom() >= 7.5 ? 1 : 0;
  if (band !== state.zoomBand) {
    state.zoomBand = band;
    if (data.cells.length) render();
  }
});
