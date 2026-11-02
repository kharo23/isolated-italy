/** Pure geometry helpers (no DOM, no map). Coordinates are [longitude, latitude] in degrees. */

const KM_PER_DEGREE = 111.19;

/**
 * Nearest point in a flat array of interleaved lon/lat values.
 * Uses an equirectangular approximation, accurate enough for the distances shown here.
 * @param {Float32Array|number[]} flat
 * @returns {{lon: number, lat: number, km: number}}
 */
export function nearestPoint(flat, lon, lat) {
  const scale = Math.cos((lat * Math.PI) / 180);
  let best = Infinity;
  let index = -1;
  for (let i = 0; i < flat.length; i += 2) {
    const dx = (flat[i] - lon) * scale;
    const dy = flat[i + 1] - lat;
    const d = dx * dx + dy * dy;
    if (d < best) {
      best = d;
      index = i;
    }
  }
  return { lon: flat[index], lat: flat[index + 1], km: Math.sqrt(best) * KM_PER_DEGREE };
}

/** Ray-casting point-in-ring test. */
export function pointInRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

const polygonsOf = (geometry) => (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates);

/** Whether a point lies in a Polygon/MultiPolygon, honouring holes. */
export function pointInGeometry(x, y, geometry) {
  return polygonsOf(geometry).some(
    (polygon) => pointInRing(x, y, polygon[0]) && !polygon.slice(1).some((hole) => pointInRing(x, y, hole)),
  );
}

/** Number of points of a flat lon/lat array that fall inside a Polygon/MultiPolygon. */
export function countInGeometry(flat, geometry) {
  let west = Infinity;
  let east = -Infinity;
  let south = Infinity;
  let north = -Infinity;
  for (const polygon of polygonsOf(geometry)) {
    for (const [x, y] of polygon[0]) {
      if (x < west) west = x;
      if (x > east) east = x;
      if (y < south) south = y;
      if (y > north) north = y;
    }
  }
  let count = 0;
  for (let i = 0; i < flat.length; i += 2) {
    const x = flat[i];
    const y = flat[i + 1];
    if (x >= west && x <= east && y >= south && y <= north && pointInGeometry(x, y, geometry)) count++;
  }
  return count;
}

export const insideItaly = (lon, lat, bounds) =>
  lon >= bounds.west && lon <= bounds.east && lat >= bounds.south && lat <= bounds.north;
