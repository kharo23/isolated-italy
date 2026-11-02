/** Ready-made entry points: the featured example and the top pharmacy sites. */

import { analyse } from "./analysis.js";
import { ITALY_CENTER } from "./config.js";
import { render } from "./layers.js";
import { map } from "./map.js";
import { setMetric } from "./panel.js";
import { closeSites } from "./sites.js";
import { stopTour } from "./tourRunner.js";
import { $, esc, isMobile } from "./util.js";

/** The first six pharmacy sites; their routing answers are pre-warmed in the cache. */
const PLACES = [
  { name: "Castelnuovo Berardenga", lon: 11.43177, lat: 43.33951 },
  { name: "Fondi", lon: 13.37147, lat: 41.28737 },
  { name: "Umbertide", lon: 12.36189, lat: 43.23239 },
  { name: "Troia", lon: 15.47064, lat: 41.39283 },
  { name: "Magliano in Toscana", lon: 11.32482, lat: 42.54688 },
  { name: "Acate", lon: 14.38223, lat: 36.97165 },
];

async function goToPlace(place) {
  stopTour();
  closeSites();
  map.flyTo({ center: [place.lon, place.lat], zoom: 10.2, duration: 1800, essential: true });
  await analyse(place.lon, place.lat, null);
}

export function initPlaces() {
  $("chips").innerHTML = PLACES.map((p, i) => `<button data-i="${i}">${esc(p.name)}</button>`).join("");
  $("chips").onclick = (event) => {
    const button = event.target.closest("button");
    if (button) goToPlace(PLACES[Number(button.dataset.i)]);
  };
  $("hero").onclick = () => {
    setMetric("conflict");
    render();
    map.flyTo({ center: ITALY_CENTER, zoom: isMobile() ? 4.2 : 5.3, duration: 1200 });
  };
}
