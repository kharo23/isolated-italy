"""Stage 1: count Overture buildings per H3 cell over Italy.

Only the bounding box columns are read (no geometry), which keeps the scan cheap. Footprint area is approximated
from the bounding box. Output: ``data/buildings_r<resolution>.parquet`` with columns ``cell`` and ``n``.
"""

from __future__ import annotations

import argparse
import logging
import time

from . import config
from .db import connect

log = logging.getLogger(__name__)


def build_query(resolution: int, out_path: str) -> str:
    """Return the COPY statement that aggregates qualifying buildings per H3 cell."""
    lon_min, lat_min, lon_max, lat_max = config.BUILDINGS_BBOX
    area_min, area_max = config.FOOTPRINT_M2
    classes = ",".join(f"'{c}'" for c in config.OUTBUILDING_CLASSES)
    subtypes = ",".join(f"'{s}'" for s in config.OUTBUILDING_SUBTYPES)
    return f"""
    COPY (
      SELECT h3_latlng_to_cell_string((bbox.ymin + bbox.ymax) / 2, (bbox.xmin + bbox.xmax) / 2, {resolution}) AS cell,
             count(*)::INT AS n
      FROM read_parquet('{config.OVERTURE_BASE}/theme=buildings/type=building/*', hive_partitioning=1)
      WHERE bbox.xmin BETWEEN {lon_min} AND {lon_max} AND bbox.ymin BETWEEN {lat_min} AND {lat_max}
        AND (bbox.xmax - bbox.xmin) * (bbox.ymax - bbox.ymin) * 111000 * 111000
            * cos(radians((bbox.ymin + bbox.ymax) / 2)) BETWEEN {area_min} AND {area_max}
        AND coalesce(class, '') NOT IN ({classes})
        AND coalesce(subtype, '') NOT IN ({subtypes})
      GROUP BY 1
    ) TO '{out_path}' (FORMAT parquet)
    """


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution", type=int, choices=(8, 9), default=8, help="H3 resolution (default: 8)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    out = config.DATA_DIR / f"buildings_r{args.resolution}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    con = connect(remote=True, h3=True)
    con.execute(build_query(args.resolution, str(out)))
    cells, buildings = con.execute(f"SELECT count(*), sum(n) FROM '{out}'").fetchone()
    log.info("%s: %d cells, %d buildings in %.0f s", out, cells, buildings, time.time() - started)


if __name__ == "__main__":
    main()
