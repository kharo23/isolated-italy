import { describe, expect, it } from "vitest";
import { countInGeometry, insideItaly, nearestPoint, pointInGeometry, pointInRing } from "../src/geo.js";

const square = [
  [0, 0],
  [10, 0],
  [10, 10],
  [0, 10],
  [0, 0],
];
const hole = [
  [4, 4],
  [6, 4],
  [6, 6],
  [4, 6],
  [4, 4],
];

describe("pointInRing", () => {
  it("detects inside and outside", () => {
    expect(pointInRing(5, 5, square)).toBe(true);
    expect(pointInRing(11, 5, square)).toBe(false);
  });
});

describe("pointInGeometry", () => {
  it("honours holes", () => {
    const polygon = { type: "Polygon", coordinates: [square, hole] };
    expect(pointInGeometry(2, 2, polygon)).toBe(true);
    expect(pointInGeometry(5, 5, polygon)).toBe(false);
  });

  it("supports MultiPolygon", () => {
    const multi = {
      type: "MultiPolygon",
      coordinates: [
        [square],
        [
          [
            [20, 20],
            [30, 20],
            [30, 30],
            [20, 30],
            [20, 20],
          ],
        ],
      ],
    };
    expect(pointInGeometry(25, 25, multi)).toBe(true);
    expect(pointInGeometry(15, 15, multi)).toBe(false);
  });
});

describe("countInGeometry", () => {
  it("counts only points inside", () => {
    const flat = new Float32Array([1, 1, 5, 5, 20, 20, 9, 9]);
    expect(countInGeometry(flat, { type: "Polygon", coordinates: [square] })).toBe(3);
  });
});

describe("nearestPoint", () => {
  it("returns the closest point and its distance", () => {
    const flat = new Float32Array([10, 40, 12, 41]);
    const result = nearestPoint(flat, 12, 41.1);
    expect(result.lon).toBeCloseTo(12);
    expect(result.lat).toBeCloseTo(41);
    expect(result.km).toBeGreaterThan(10);
    expect(result.km).toBeLessThan(12);
  });
});

describe("insideItaly", () => {
  const bounds = { west: 6.5, south: 35.3, east: 18.9, north: 47.2 };
  it("accepts Rome and rejects Paris", () => {
    expect(insideItaly(12.5, 41.9, bounds)).toBe(true);
    expect(insideItaly(2.35, 48.85, bounds)).toBe(false);
  });
});
