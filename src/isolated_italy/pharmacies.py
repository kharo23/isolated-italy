"""Stage 4: merge the Ministry of Health pharmacy register into the service layer.

Overture misses many pharmacies and the register has coordinate errors of its own, so the layer used for distances
is the union of both sources: a place is isolated only if neither source has a pharmacy nearby.

* Register: active entries of the open "Farmacie" dataset. Entries without coordinates are placed at the
  building-weighted centre of their comune, matched by normalised name and province.
* Overture pharmacies that lie more than ``DEDUP_KM`` from every register entry are added to the union.

Inputs: ``data/official_farmacie/farmacie.csv``, ``data/services_overture.parquet``, ``data/cells_admin.parquet``.
Output: ``data/services.parquet`` (all categories; register pharmacies carry ids prefixed ``MinSal-``).
"""

from __future__ import annotations

import argparse
import logging
import re
import unicodedata

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from . import config
from .db import connect
from .geo import km_from_chord, unit_vectors

log = logging.getLogger(__name__)

DEDUP_KM = 0.3
REGISTER_PREFIX = "MinSal-"


def normalise(text: object) -> str:
    """Lower-case ASCII form of a place name, used to match register names to Overture names."""
    ascii_text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    ascii_text = re.sub(r"[^a-z ]", " ", ascii_text.replace("'", ""))
    return re.sub(r"\s+", " ", ascii_text).strip()


def read_register(path: str) -> list[tuple]:
    """Return active register rows as (name, comune, provincia, regione, lat, lon)."""
    con = connect()
    return con.execute(f"""
        WITH f AS (
          SELECT *,
                 try_strptime(data_fine_validita, '%d/%m/%Y') AS ends,
                 try_strptime(data_inizio_validita, '%d/%m/%Y') AS starts
          FROM read_csv('{path}', delim=';', header=true, all_varchar=true, quote='"', ignore_errors=true))
        SELECT descrizione_farmacia, comune, provincia, regione,
               try_cast(replace(latitudine, ',', '.') AS DOUBLE), try_cast(replace(longitudine, ',', '.') AS DOUBLE)
        FROM f WHERE (ends IS NULL OR ends > current_date) AND starts <= current_date""").fetchall()


def comune_centres(cells_path: str) -> tuple[dict, dict]:
    """Building-weighted centre per (comune, province) and per comune name, from the admin cell table."""
    con = connect()
    rows = con.execute(f"""
        SELECT comune, prov, sum(lat * n) / sum(n), sum(lon * n) / sum(n)
        FROM '{cells_path}' WHERE comune IS NOT NULL GROUP BY 1, 2""").fetchall()
    by_pair: dict[tuple[str, str], tuple[float, float]] = {}
    by_name: dict[str, list[tuple[float, float]]] = {}
    for comune, prov, lat, lon in rows:
        for part in {comune.split("/")[0], comune.split("/")[-1]}:
            by_pair[(normalise(part), normalise(prov))] = (lat, lon)
        by_name.setdefault(normalise(comune), []).append((lat, lon))
    return by_pair, by_name


def place_register(rows: list[tuple], cells_path: str) -> tuple[list[tuple], dict[str, int]]:
    """Return placed register pharmacies as (name, lat, lon, region) plus placement counts."""
    lon_min, lat_min, lon_max, lat_max = config.ITALY_BBOX
    by_pair, by_name = comune_centres(cells_path)
    placed: list[tuple] = []
    counts = {"own": 0, "comune_centre": 0, "unplaced": 0}
    for name, comune, prov, region, lat, lon in rows:
        if lat is not None and lon is not None and lat_min < lat < lat_max and lon_min < lon < lon_max:
            placed.append((name, lat, lon, region))
            counts["own"] += 1
            continue
        centre = by_pair.get((normalise(comune), normalise(prov)))
        if centre is None:
            candidates = by_name.get(normalise(comune), [])
            centre = candidates[0] if len(candidates) == 1 else None
        if centre is None:
            counts["unplaced"] += 1
        else:
            placed.append((name, centre[0], centre[1], region))
            counts["comune_centre"] += 1
    return placed, counts


def overture_only(overture_pharmacies: pa.Table, register_latlon: np.ndarray) -> pa.Table:
    """Overture pharmacies farther than ``DEDUP_KM`` from every register entry."""
    from scipy.spatial import cKDTree

    tree = cKDTree(unit_vectors(register_latlon[:, 0], register_latlon[:, 1]))
    queries = unit_vectors(
        overture_pharmacies["lat"].to_numpy(zero_copy_only=False),
        overture_pharmacies["lon"].to_numpy(zero_copy_only=False),
    )
    chord, _ = tree.query(queries)
    return overture_pharmacies.filter(pa.array(km_from_chord(chord) > DEDUP_KM))


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    rows = read_register(str(config.REGISTER_CSV))
    placed, counts = place_register(rows, str(config.DATA_DIR / "cells_admin.parquet"))
    log.info("register: %d active entries; %s", len(rows), counts)

    overture = pq.read_table(config.DATA_DIR / "services_overture.parquet")
    others = overture.filter(pc.not_equal(overture["cat"], "pharmacy"))
    schema = others.schema
    register_table = (
        pa.table(
            {
                "id": [f"{REGISTER_PREFIX}{i}" for i in range(len(placed))],
                "cat": ["pharmacy"] * len(placed),
                "tax": ["pharmacy"] * len(placed),
                "name": [p[0] for p in placed],
                "confidence": [1.0] * len(placed),
                "lon": [p[2] for p in placed],
                "lat": [p[1] for p in placed],
                "locality": [None] * len(placed),
                "region": [p[3] for p in placed],
            }
        )
        .select(schema.names)
        .cast(schema)
    )

    ov_pharm = overture.filter(
        pc.and_(
            pc.equal(overture["cat"], "pharmacy"),
            pc.greater_equal(overture["confidence"], config.MIN_CONFIDENCE),
        )
    )
    extra = overture_only(ov_pharm, np.array([(p[1], p[2]) for p in placed]))
    log.info("Overture pharmacies kept in the union: %d of %d", extra.num_rows, ov_pharm.num_rows)

    out = config.DATA_DIR / "services.parquet"
    pq.write_table(pa.concat_tables([others, register_table, extra.select(schema.names).cast(schema)]), out)
    log.info("%s written", out)


if __name__ == "__main__":
    main()
