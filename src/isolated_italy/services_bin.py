"""Stage 8: write each service category as a compact binary file for the browser.

Each file is a little-endian float32 array of interleaved longitude/latitude, used to count services inside a
drive-time area on the client. Input: ``data/services.parquet``. Output: ``web/public/data/svc_<category>.bin``.
"""

from __future__ import annotations

import argparse
import logging

import numpy as np

from . import config
from .db import connect

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config.WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    for cat in config.SERVICE_TAXONOMY:
        rows = con.execute(
            f"SELECT round(lon, 5), round(lat, 5) FROM '{config.DATA_DIR / 'services.parquet'}' "
            f"WHERE cat = '{cat}' AND confidence >= {config.MIN_CONFIDENCE}"
        ).fetchall()
        flat = np.array(rows, dtype="<f4").reshape(-1)
        flat.tofile(config.WEB_DATA_DIR / f"svc_{cat}.bin")
        log.info("%-8s %6d points, %d KB", cat, len(rows), flat.nbytes // 1024)


if __name__ == "__main__":
    main()
