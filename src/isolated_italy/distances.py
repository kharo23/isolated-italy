"""Stage 5: distance from every cell to the nearest service of each category.

Distances are straight-line (great circle). For pharmacies the distance to each source alone is also stored
(``d_phreg``: Ministry register, ``d_phov``: all Overture pharmacies) to map where the sources disagree.
Inputs: ``data/cells_admin.parquet``, ``data/services.parquet``, ``data/services_overture.parquet``.
Output: ``data/cells.parquet``.
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from . import config
from .db import connect
from .geo import nearest_km, unit_vectors
from .pharmacies import REGISTER_PREFIX

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    cells = pq.read_table(config.DATA_DIR / "cells_admin.parquet")
    queries = unit_vectors(cells["lat"].to_numpy(), cells["lon"].to_numpy())
    columns = {name: cells[name] for name in cells.column_names}

    con = connect()
    services = con.execute(
        f"SELECT cat, lat, lon, id FROM '{config.DATA_DIR / 'services.parquet'}' "
        f"WHERE cat IS NOT NULL AND confidence >= {config.MIN_CONFIDENCE}"
    ).fetchall()
    for cat in sorted({s[0] for s in services}):
        points = np.array([(s[1], s[2]) for s in services if s[0] == cat])
        dist = nearest_km(points, queries)
        columns[f"d_{cat}"] = pa.array(dist.astype("float32"))
        log.info("%-8s %6d services, median distance %.2f km", cat, len(points), np.median(dist))

    overture_pharmacies = np.array(
        con.execute(
            f"SELECT lat, lon FROM '{config.DATA_DIR / 'services_overture.parquet'}' "
            f"WHERE cat = 'pharmacy' AND confidence >= {config.MIN_CONFIDENCE}"
        ).fetchall()
    )
    register_pharmacies = np.array(
        [(s[1], s[2]) for s in services if s[0] == "pharmacy" and str(s[3]).startswith(REGISTER_PREFIX)]
    )
    for tag, points in (("phreg", register_pharmacies), ("phov", overture_pharmacies)):
        columns[f"d_{tag}"] = pa.array(nearest_km(points, queries).astype("float32"))

    out = config.DATA_DIR / "cells.parquet"
    pq.write_table(pa.table(columns), out)
    log.info("%s: %d cells", out, cells.num_rows)


if __name__ == "__main__":
    main()
