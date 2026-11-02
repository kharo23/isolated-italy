"""Stage 2: extract essential-service places in Italy from Overture Places.

Output: ``data/services_overture.parquet`` with one row per place and a ``cat`` service category.
"""

from __future__ import annotations

import argparse
import logging
import time

from . import config
from .db import connect

log = logging.getLogger(__name__)


def build_query(out_path: str) -> str:
    """Return the COPY statement selecting open places of the configured taxonomy in Italy."""
    cases = " ".join(
        f"WHEN taxonomy.primary IN ({','.join(repr(t) for t in tax)}) THEN '{cat}'"
        for cat, tax in config.SERVICE_TAXONOMY.items()
    )
    every = ",".join(repr(t) for tax in config.SERVICE_TAXONOMY.values() for t in tax)
    return f"""
    COPY (
      SELECT id, CASE {cases} END AS cat, taxonomy.primary AS tax, names.primary AS name, confidence,
             ST_X(geometry) AS lon, ST_Y(geometry) AS lat,
             addresses[1].locality AS locality, addresses[1].region AS region
      FROM read_parquet('{config.OVERTURE_BASE}/theme=places/type=place/*', hive_partitioning=1)
      WHERE addresses[1].country = 'IT' AND taxonomy.primary IN ({every})
        AND coalesce(operating_status, 'open') = 'open'
    ) TO '{out_path}' (FORMAT parquet)
    """


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = config.DATA_DIR / "services_overture.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    con = connect(remote=True, spatial=True)
    con.execute(build_query(str(out)))
    log.info("%s written in %.0f s", out, time.time() - started)
    for cat, n, conf in con.execute(
        f"SELECT cat, count(*), round(avg(confidence), 2) FROM '{out}' GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall():
        log.info("  %-8s %7d places, mean confidence %.2f", cat, n, conf)


if __name__ == "__main__":
    main()
