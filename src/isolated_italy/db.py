"""DuckDB connection helper."""

from __future__ import annotations

import duckdb

from .config import OVERTURE_REGION


def connect(*, remote: bool = False, spatial: bool = False, h3: bool = False) -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB connection with the requested extensions loaded.

    Args:
        remote: read from S3 (httpfs) with the Overture bucket region configured.
        spatial: load the spatial extension.
        h3: load the H3 community extension.
    """
    con = duckdb.connect()
    statements: list[str] = []
    if remote:
        statements += ["INSTALL httpfs", "LOAD httpfs", f"SET s3_region='{OVERTURE_REGION}'", "SET threads=8"]
    if spatial:
        statements += ["INSTALL spatial", "LOAD spatial"]
    if h3:
        statements += ["INSTALL h3 FROM community", "LOAD h3"]
    for statement in statements:
        con.execute(statement)
    return con
