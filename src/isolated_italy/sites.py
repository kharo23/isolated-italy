"""Stage 9: candidate sites for a new service, by greedy maximum coverage.

For a category and a radius R (km, straight line, the same notion of "out of reach" as the map):

* unserved cells: cells whose nearest service of the category is farther than R;
* candidate sites: the centres of unserved cells;
* gain of a site: residents of unserved cells within R of it.

The best site is picked, its catchment is marked served, and the search repeats. This is a ranking proxy:
:mod:`isolated_italy.validate` re-scores the top candidates with real drive-time areas.
Input: ``data/cells_pop.parquet``. Output: ``data/sites_proxy.json``.
"""

from __future__ import annotations

import argparse
import json
import logging

import numpy as np
import pyarrow.parquet as pq
from scipy.spatial import cKDTree

from . import config
from .coverage import greedy_cover
from .geo import chord_from_km, unit_vectors

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius-km", type=float, default=config.THRESHOLD_KM)
    parser.add_argument("--top", type=int, default=40, help="candidates kept per category")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    table = pq.read_table(config.DATA_DIR / "cells_pop.parquet")
    col = {name: table[name].to_numpy(zero_copy_only=False) for name in table.column_names}
    chord = chord_from_km(args.radius_km)
    result: dict = {"radius_km": args.radius_km, "categories": {}}

    for cat in config.SITE_CATEGORIES:
        unserved = np.where(col[f"d_{cat}"] > args.radius_km)[0]
        points = unit_vectors(col["lat"][unserved], col["lon"][unserved])
        residents = col["pop"][unserved].astype(np.int64)
        neighbours = cKDTree(points).query_ball_point(points, chord)
        picks = greedy_cover(residents, neighbours, args.top)
        sites = []
        for rank, (i, gain) in enumerate(picks, start=1):
            k = unserved[i]
            sites.append(
                {
                    "rank": rank,
                    "lon": round(float(col["lon"][k]), 5),
                    "lat": round(float(col["lat"][k]), 5),
                    "gain": gain,
                    "comune": col["comune"][k],
                    "prov": col["prov"][k],
                }
            )
        total = int(residents.sum())
        covered = sum(s["gain"] for s in sites)
        result["categories"][cat] = {
            "unserved": total,
            "unserved_cells": int(len(unserved)),
            "top_gain": covered,
            "sites": sites,
        }
        log.info(
            "%-8s %d residents unserved, top %d sites cover %d (%.1f%%)",
            cat,
            total,
            args.top,
            covered,
            100 * covered / total,
        )

    out = config.DATA_DIR / "sites_proxy.json"
    out.write_text(json.dumps(result, ensure_ascii=False))
    log.info("%s written", out)


if __name__ == "__main__":
    main()
