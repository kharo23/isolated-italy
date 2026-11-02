/** Shared application state. Modules read and mutate it directly; rendering is triggered explicitly. */

import { DEFAULT_THRESHOLD_KM } from "./config.js";

export const state = {
  metric: "count", // count | pharmacy | health | school | grocery | post | train | conflict
  threshold: DEFAULT_THRESHOLD_KM,
  extrude: false,
  hovered: null,
  isoline: null, // GeoJSON geometry drawn on the map
  pin: null,
  zoomBand: 0,
  siteCategory: null,
  siteIndex: null,
  /** Incremented to invalidate in-flight asynchronous work (stale responses are dropped). */
  requestId: 0,
};

export const data = {
  cells: [],
  localities: [],
  headline: null,
  sites: null,
  services: {},
};
