"""Stage 3: attach province, region and locality to every building cell.

Cells are matched to Overture division polygons by their centre. A cell that no province claims (Overture has no
province level for Valle d'Aosta) falls back to its region polygon. Cells outside every polygon are outside Italy and
are dropped. Output: ``data/cells_admin.parquet``.
"""

from __future__ import annotations

import argparse
import logging

from . import config
from .db import connect

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    con = connect(remote=True, spatial=True, h3=True)
    divisions = f"{config.OVERTURE_BASE}/theme=divisions/type=division_area/*"

    for subtype, table in (("county", "province"), ("locality", "locality"), ("region", "region")):
        con.execute(f"""
            CREATE TABLE {table} AS
            SELECT id, names.primary AS name, region, geometry AS geom
            FROM read_parquet('{divisions}', hive_partitioning=1)
            WHERE country = 'IT' AND subtype = '{subtype}' AND class = 'land'""")
        log.info("%s polygons: %d", table, con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])

    con.execute(f"""
        CREATE TABLE pts AS
        SELECT cell, n, h3_cell_to_lat(cell) AS lat, h3_cell_to_lng(cell) AS lon,
               ST_Point(h3_cell_to_lng(cell), h3_cell_to_lat(cell)) AS p
        FROM '{config.DATA_DIR / "buildings_r8.parquet"}'""")
    con.execute("""
        CREATE TABLE in_province AS
        SELECT pts.cell, any_value(pts.n) AS n, any_value(pts.lat) AS lat, any_value(pts.lon) AS lon,
               any_value(province.name) AS province, any_value(province.region) AS region
        FROM pts JOIN province ON ST_Within(pts.p, province.geom) GROUP BY pts.cell""")
    con.execute("""
        INSERT INTO in_province
        SELECT pts.cell, any_value(pts.n), any_value(pts.lat), any_value(pts.lon),
               any_value(region.name), any_value(region.name)
        FROM pts JOIN region ON ST_Within(pts.p, region.geom)
        WHERE pts.cell NOT IN (SELECT cell FROM in_province) GROUP BY pts.cell""")
    out = config.DATA_DIR / "cells_admin.parquet"
    con.execute(f"""
        COPY (
          SELECT p.cell, p.n, p.lat, p.lon, p.province AS prov, p.region, any_value(locality.name) AS comune
          FROM in_province p
          LEFT JOIN locality ON ST_Within(ST_Point(p.lon, p.lat), locality.geom)
          GROUP BY p.cell, p.n, p.lat, p.lon, p.province, p.region
        ) TO '{out}' (FORMAT parquet)""")
    cells, buildings = con.execute(f"SELECT count(*), sum(n) FROM '{out}'").fetchone()
    log.info("%s: %d cells, %d buildings", out, cells, buildings)


if __name__ == "__main__":
    main()
