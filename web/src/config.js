/** Application constants. */

export const API_BASE = import.meta.env.VITE_API_BASE || "";
export const AWS_REGION = import.meta.env.VITE_AWS_REGION || "eu-central-1";
export const IDENTITY_POOL_ID = import.meta.env.VITE_IDENTITY_POOL_ID || "";

/** Services counted in the "out of reach" index. */
export const ESSENTIAL = ["pharmacy", "health", "school", "grocery", "post"];
/** All services shown in tables and tooltips. */
export const SERVICES = [...ESSENTIAL, "train"];
/** Services for which a road route is requested (keeps the routing bill small). */
export const ROUTED = ["pharmacy", "health", "school"];

export const SERVICE_LABEL = {
  pharmacy: "Pharmacy",
  health: "Doctor / hospital",
  school: "School",
  grocery: "Grocery",
  post: "Post office",
  train: "Train station",
};
export const SITE_LABEL = { pharmacy: "pharmacy", health: "doctor or hospital", school: "school" };

/** Distance thresholds (km) offered by the slider; must match THRESHOLD_STEPS in the pipeline. */
export const THRESHOLD_STEPS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20];
export const DEFAULT_THRESHOLD_KM = 5;

export const ITALY_BOUNDS = { west: 6.5, south: 35.3, east: 18.9, north: 47.2 };
export const ITALY_CENTER = [12.5, 42.0];
export const MOBILE_BREAKPOINT = 700;

/** Sequential, colour-blind-safe ramp: brighter means more isolated. */
export const RAMP = [
  [39, 49, 66],
  [60, 90, 160],
  [33, 150, 140],
  [94, 201, 98],
  [190, 223, 38],
  [253, 231, 37],
];

export const FALLBACK_STYLE = "https://demotiles.maplibre.org/style.json";
export const REACH_MINUTES = 15;
