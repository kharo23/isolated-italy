/** Map instance: Amazon Location basemap through MapLibre, with a deck.gl overlay. */

import { withIdentityPoolId } from "@aws/amazon-location-utilities-auth-helper";
import { MapboxOverlay } from "@deck.gl/mapbox";
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { AWS_REGION, FALLBACK_STYLE, IDENTITY_POOL_ID, ITALY_BOUNDS, ITALY_CENTER } from "./config.js";
import { $, isMobile } from "./util.js";

maplibregl.setWorkerUrl(workerUrl);

const styleUrl = (name, scheme) =>
  `https://maps.geo.${AWS_REGION}.amazonaws.com/v2/styles/${name}/descriptor?color-scheme=${scheme}`;

async function createAuth() {
  if (!IDENTITY_POOL_ID) {
    $("banner").textContent = "Development mode: no identity pool configured, using a placeholder basemap.";
    return null;
  }
  try {
    return await withIdentityPoolId(IDENTITY_POOL_ID);
  } catch (error) {
    console.warn("Amazon Location authentication failed", error);
    return null;
  }
}

const auth = await createAuth();

export const map = new maplibregl.Map({
  container: "map",
  style: auth ? styleUrl("Monochrome", "Dark") : FALLBACK_STYLE,
  ...(auth ? auth.getMapAuthenticationOptions() : {}),
  center: ITALY_CENTER,
  zoom: isMobile() ? 4.2 : 5.2,
  minZoom: 4,
  maxZoom: 15,
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

let fellBack = false;
map.on("error", (event) => {
  if (auth && event?.error?.status && !fellBack && !map.isStyleLoaded()) {
    fellBack = true;
    map.setStyle(FALLBACK_STYLE);
    $("banner").textContent = "Basemap style unavailable, using a placeholder.";
  }
});

/** Fit Italy in the area not covered by the side panel (bottom sheet on small screens). */
export function showItaly(animate = true) {
  const mobile = isMobile();
  map.fitBounds(
    [
      [ITALY_BOUNDS.west + 0.4, ITALY_BOUNDS.south + 1.2],
      [ITALY_BOUNDS.east - 0.4, ITALY_BOUNDS.north - 0.1],
    ],
    {
      padding: mobile
        ? { top: 90, left: 8, right: 8, bottom: Math.round(window.innerHeight * 0.5) }
        : { top: 20, left: 400, right: 20, bottom: 20 },
      animate,
      duration: 1200,
    },
  );
}

export const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
map.addControl(overlay);

export const Marker = maplibregl.Marker;
