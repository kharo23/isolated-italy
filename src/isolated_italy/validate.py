"""Stage 10: re-score candidate sites with real drive-time areas from Amazon Location Service.

For each of the top candidates, a 15-minute car isoline is requested (``CalculateIsolines``). The road gain of a site is
the number of residents in currently unserved cells whose centre falls inside the isoline. Sites are ranked by road
gain; the straight-line gain is kept for comparison. Isolines are cached on disk so a site is never requested twice.

Needs AWS credentials. Input: ``data/sites_proxy.json``, ``data/cells_pop.parquet``. Output: ``data/sites.json``.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

import boto3
import numpy as np
import pyarrow.parquet as pq
from botocore.exceptions import ClientError
from shapely import contains_xy
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry

from . import config

log = logging.getLogger(__name__)

MINUTES = 15
SIMPLIFY_DEGREES = 0.0008  # about 80 m
CACHE_PATH = config.DATA_DIR / "isoline_cache.json"


def road_gain(isoline: BaseGeometry, lon: np.ndarray, lat: np.ndarray, residents: np.ndarray) -> int:
    """Residents of the given cells whose centre lies inside ``isoline``."""
    return int(residents[contains_xy(isoline, lon, lat)].sum())


def to_multipolygon(geometries: list[dict]) -> MultiPolygon:
    """Build a MultiPolygon from the ``Geometries`` of a CalculateIsolines response (outer ring first)."""
    polygons = [Polygon(g["Polygon"][0], g["Polygon"][1:]).buffer(0) for g in geometries if "Polygon" in g]
    return MultiPolygon([p for p in polygons if not p.is_empty])


class IsolineSource:
    """Isolines from Amazon Location Service with an on-disk cache."""

    def __init__(self, region: str) -> None:
        self.client = boto3.client("geo-routes", region_name=region)
        self.cache: dict[str, dict] = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
        self.api_calls = 0

    def get(self, lon: float, lat: float) -> BaseGeometry | None:
        key = f"{lon},{lat}"
        if key not in self.cache:
            geometry = self._request(lon, lat)
            if geometry is None:
                return None
            self.cache[key] = mapping(geometry.simplify(SIMPLIFY_DEGREES, preserve_topology=True))
        return shape(self.cache[key])

    def _request(self, lon: float, lat: float) -> MultiPolygon | None:
        self.api_calls += 1
        for attempt in range(3):
            try:
                response = self.client.calculate_isolines(
                    Origin=[lon, lat],
                    Thresholds={"Time": [MINUTES * 60]},
                    TravelMode="Car",
                    IsolineGeometryFormat="Simple",
                )
                return to_multipolygon(response["Isolines"][0]["Geometries"])
            except ClientError as error:
                if "could not be matched" in str(error):
                    return None  # the point is not on the road network
                time.sleep(1.5 * (attempt + 1))
        return None

    def save(self) -> None:
        CACHE_PATH.write_text(json.dumps(self.cache))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="eu-central-1")
    parser.add_argument("--top", type=int, default=25, help="candidates validated per category")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    proxy = json.loads((config.DATA_DIR / "sites_proxy.json").read_text())
    radius = proxy["radius_km"]
    table = pq.read_table(config.DATA_DIR / "cells_pop.parquet")
    col = {name: table[name].to_numpy(zero_copy_only=False) for name in table.column_names}
    source = IsolineSource(args.region)
    result: dict = {"radius_km": radius, "minutes": MINUTES, "categories": {}}

    for cat, entry in proxy["categories"].items():
        candidates = entry["sites"][: args.top]
        unserved = col[f"d_{cat}"] > radius
        ux, uy, uw = col["lon"][unserved], col["lat"][unserved], col["pop"][unserved].astype(np.int64)
        with ThreadPoolExecutor(4) as pool:
            isolines = list(pool.map(lambda s: source.get(s["lon"], s["lat"]), candidates))
        sites, union = [], np.zeros(len(ux), dtype=bool)
        for site, isoline in zip(candidates, isolines, strict=True):
            if isoline is None or isoline.is_empty:
                continue
            gain = road_gain(isoline, ux, uy, uw)
            union |= contains_xy(isoline, ux, uy)
            sites.append(
                {
                    **site,
                    "road_gain": gain,
                    "ratio": round(gain / site["gain"], 2) if site["gain"] else None,
                    "isoline": mapping(isoline),
                }
            )
        sites.sort(key=lambda s: -s["road_gain"])
        for rank, site in enumerate(sites, start=1):
            site["rank"] = rank
        ratios = [s["ratio"] for s in sites if s["ratio"]]
        result["categories"][cat] = {
            "unserved": entry["unserved"],
            "validated": len(sites),
            "union_gain": int(uw[union].sum()),
            "median_ratio": float(np.median(ratios)),
            "sites": sites,
        }
        log.info(
            "%-8s %d sites, union gain %d of %d, median road/straight-line ratio %.2f",
            cat,
            len(sites),
            int(uw[union].sum()),
            entry["unserved"],
            np.median(ratios),
        )

    out = config.DATA_DIR / "sites.json"
    out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    config.WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(out, config.WEB_DATA_DIR / "sites.json")
    source.save()
    log.info("%s written; Amazon Location isoline requests this run: %d", out, source.api_calls)


if __name__ == "__main__":
    main()
