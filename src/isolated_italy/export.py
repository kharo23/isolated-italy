"""Stage 7: aggregate cells into the files the web app loads (``web/public/data``).

* ``cells7.json``: resolution-7 display cells, as column arrays.
* ``comuni.json`` / ``province.json``: per-locality and per-province aggregates.
* ``headline.json``: national totals.

Every share is resident-weighted. A resident counts as "far" from a service when the nearest one is beyond
``THRESHOLD_KM`` in a straight line.
"""

from __future__ import annotations

import argparse
import json
import logging

from . import config
from .db import connect

log = logging.getLogger(__name__)

DISTANCE_COLUMNS = [*config.ESSENTIAL, "train"]


def far_count(threshold: float) -> str:
    """SQL expression: number of essential services farther than ``threshold`` km."""
    return " + ".join(f"(d_{c} > {threshold})::INT" for c in config.ESSENTIAL)


def weighted_mean(column: str, digits: int = 1) -> str:
    return f"round(sum({column} * pop) / sum(pop), {digits})"


def display_cells(con) -> dict[str, list]:
    """Resolution-7 cells with residents, per-threshold mean far counts and mean distances."""
    thresholds = ", ".join(
        f"round(sum(({far_count(t)}) * pop) * 1.0 / sum(pop), 2) AS nf_{t}" for t in config.THRESHOLD_STEPS
    )
    distances = ", ".join(f"{weighted_mean(f'd_{c}')} AS d_{c}" for c in DISTANCE_COLUMNS)
    rows = con.execute(f"""
        SELECT h3_cell_to_parent(cell, 7) AS h, round(sum(pop))::INT AS n, {thresholds}, {distances},
               round(sum(CASE WHEN (d_phreg > {config.THRESHOLD_KM}) != (d_phov > {config.THRESHOLD_KM})
                              THEN pop ELSE 0 END) * 1.0 / sum(pop), 2) AS cf,
               round(sum(CASE WHEN nfar >= 3 THEN pop ELSE 0 END) * 1.0 / sum(pop), 2) AS iso3,
               round(sum(nfar * pop) * 1.0 / sum(pop), 2) AS nfar
        FROM c GROUP BY 1""")
    names = [d[0] for d in rows.description]
    data = rows.fetchall()
    return {name: [r[i] for r in data] for i, name in enumerate(names)}


def area_table(con, group: str, key: str) -> list[dict]:
    """Aggregates per area. ``group`` is the displayed name, ``key`` the GROUP BY expression."""
    distances = ", ".join(f"{weighted_mean(f'd_{c}')} AS d_{c}" for c in DISTANCE_COLUMNS)
    province = "prov" if key != group else "any_value(prov)"
    rows = con.execute(f"""
        SELECT {group} AS name, {province} AS prov, any_value(region) AS region, round(sum(pop))::INT AS n,
               round(sum(lat * pop) / sum(pop), 4) AS lat, round(sum(lon * pop) / sum(pop), 4) AS lon, {distances},
               sum(CASE WHEN nfar >= 3 THEN pop ELSE 0 END)::INT AS n_iso3,
               round(sum(CASE WHEN nfar >= 3 THEN pop ELSE 0 END) * 1.0 / sum(pop), 3) AS iso3,
               sum(CASE WHEN nfar >= 1 THEN pop ELSE 0 END)::INT AS n_far1
        FROM c WHERE {group} IS NOT NULL GROUP BY {key}""")
    names = [d[0] for d in rows.description]
    return [dict(zip(names, r, strict=True)) for r in rows.fetchall()]


def headline(con) -> dict:
    t = config.THRESHOLD_KM
    total, far1, far3, far5 = con.execute("""
        SELECT sum(pop),
               sum(CASE WHEN nfar >= 1 THEN pop ELSE 0 END),
               sum(CASE WHEN nfar >= 3 THEN pop ELSE 0 END),
               sum(CASE WHEN nfar = 5 THEN pop ELSE 0 END)
        FROM c""").fetchone()
    both, ov_near, reg_near = con.execute(f"""
        SELECT sum(CASE WHEN d_phreg > {t} AND d_phov > {t} THEN pop ELSE 0 END),
               sum(CASE WHEN d_phreg > {t} AND d_phov <= {t} THEN pop ELSE 0 END),
               sum(CASE WHEN d_phreg <= {t} AND d_phov > {t} THEN pop ELSE 0 END) FROM c""").fetchone()
    union = con.execute(f"SELECT sum(CASE WHEN d_pharmacy > {t} THEN pop ELSE 0 END) FROM c").fetchone()[0]
    return {
        "total": int(total),
        "unit": "residents",
        "far1": int(far1),
        "far3": int(far3),
        "far5": int(far5),
        "thr_km": t,
        "release": config.OVERTURE_RELEASE,
        "cats": list(config.ESSENTIAL),
        "pharm_both": int(both),
        "pharm_only_overture_says_near": int(ov_near),
        "pharm_only_register_says_near": int(reg_near),
        "pharm_union": int(union),
    }


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = config.WEB_DATA_DIR
    out.mkdir(parents=True, exist_ok=True)

    con = connect(h3=True)
    con.execute(f"""
        CREATE TABLE c AS SELECT *, ({far_count(config.THRESHOLD_KM)}) AS nfar
        FROM '{config.DATA_DIR / "cells_pop.parquet"}' WHERE pop > 0""")

    cells = display_cells(con)
    (out / "cells7.json").write_text(json.dumps(cells, separators=(",", ":")))
    localities = area_table(con, "comune", "comune, prov")
    provinces = area_table(con, "prov", "prov")
    (out / "comuni.json").write_text(json.dumps(localities, separators=(",", ":"), ensure_ascii=False))
    (out / "province.json").write_text(json.dumps(provinces, separators=(",", ":"), ensure_ascii=False))
    summary = headline(con)
    (out / "headline.json").write_text(json.dumps(summary))
    log.info("%d display cells, %d localities, %d provinces", len(cells["h"]), len(localities), len(provinces))
    log.info("%s", summary)


if __name__ == "__main__":
    main()
