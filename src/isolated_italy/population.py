"""Stage 6: modelled residents per cell (dasymetric mapping).

GHS-POP R2023A (epoch 2025, 30 arc-second, ~1 km) is read anonymously from the JRC bucket. Each pixel's residents
are spread over the H3 resolution-9 building cells inside the pixel in proportion to their building counts, then
summed into their resolution-8 parent. Allocating on resolution 9 matters: a resolution-8 cell centre does not fall
in every ~1 km pixel, so allocating on resolution 8 loses those pixels.

The result is a modelled estimate, not a census count. Inputs: ``data/buildings_r9.parquet``, ``data/cells.parquet``.
Output: ``data/cells_pop.parquet`` (cells plus integer ``pop``).
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
from rasterio.windows import from_bounds

from . import config
from .db import connect

log = logging.getLogger(__name__)


def read_population_window() -> tuple[np.ndarray, rasterio.Affine]:
    """Read the Italy window of the raster; returns (pixel residents, affine transform)."""
    with (
        rasterio.Env(AWS_NO_SIGN_REQUEST="YES", AWS_REGION="eu-central-1", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"),
        rasterio.open(config.GHS_POP_URL) as dataset,
    ):
        window = from_bounds(*config.ITALY_BBOX, dataset.transform).round_offsets().round_lengths()
        pixels = dataset.read(1, window=window)
        transform = dataset.window_transform(window)
    return np.where(np.isfinite(pixels) & (pixels > 0), pixels, 0).astype("float64"), transform


def allocate(
    pixels: np.ndarray, transform: rasterio.Affine, lat: np.ndarray, lon: np.ndarray, buildings: np.ndarray
) -> np.ndarray:
    """Spread each pixel's residents over the building cells inside it, proportionally to building counts."""
    col, row = ~transform * (lon, lat)
    col, row = np.floor(col).astype(int), np.floor(row).astype(int)
    inside = (col >= 0) & (col < pixels.shape[1]) & (row >= 0) & (row < pixels.shape[0])
    pixel_id = np.where(inside, row * pixels.shape[1] + col, 0)
    buildings_per_pixel = np.bincount(pixel_id[inside], weights=buildings[inside], minlength=pixels.size)
    residents = pixels.reshape(-1)
    share = np.zeros(len(buildings))
    usable = inside & (buildings_per_pixel[pixel_id] > 0)
    share[usable] = residents[pixel_id[usable]] * buildings[usable] / buildings_per_pixel[pixel_id[usable]]
    return share


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    pixels, transform = read_population_window()
    log.info("raster window %s, %d residents including neighbouring countries", pixels.shape, pixels.sum())

    con = connect(h3=True)
    rows = con.execute(f"""
        SELECT n, h3_cell_to_lat(cell), h3_cell_to_lng(cell), h3_cell_to_parent(cell, 8)
        FROM '{config.DATA_DIR / "buildings_r9.parquet"}'""").fetchall()
    buildings = np.array([r[0] for r in rows], dtype="float64")
    lat = np.array([r[1] for r in rows])
    lon = np.array([r[2] for r in rows])
    parents = [r[3] for r in rows]
    share = allocate(pixels, transform, lat, lon, buildings)

    per_parent: dict[str, float] = {}
    for parent, value in zip(parents, share, strict=True):
        per_parent[parent] = per_parent.get(parent, 0.0) + value
    cells = pq.read_table(config.DATA_DIR / "cells.parquet")
    pop = np.array([round(per_parent.get(c, 0.0)) for c in cells["cell"].to_pylist()], dtype="int64")
    log.info("residents allocated to resolution-9 cells: %d; kept in the Italian table: %d", share.sum(), pop.sum())

    out = config.DATA_DIR / "cells_pop.parquet"
    pq.write_table(cells.append_column("pop", pa.array(pop)), out)
    log.info("%s: %d cells with residents", out, int((pop > 0).sum()))


if __name__ == "__main__":
    main()
