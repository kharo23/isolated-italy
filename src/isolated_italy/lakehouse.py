"""Stage 11: load the cell table into an Apache Iceberg table on S3 and query it with Amazon Athena.

Athena recomputes the national headline numbers from the Iceberg table; they must equal the numbers that the
DuckDB export produced (``web/public/data/headline.json``), otherwise the stage fails. This checks that two engines
agree on the same table; it does not validate the population model.

Needs AWS credentials. The data lives in a private bucket ``isolated-italy-lake-<account id>``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

import boto3
from botocore.exceptions import ClientError

from . import config

log = logging.getLogger(__name__)

DATABASE = "isolated_italy"
WORKGROUP = "isolated-italy"


class Athena:
    """Minimal synchronous Athena client bound to one workgroup and database."""

    def __init__(self, region: str) -> None:
        self.client = boto3.client("athena", region_name=region)

    def run(self, sql: str, *, database: str = DATABASE, fetch: bool = False) -> list[list[str | None]]:
        query_id = self.client.start_query_execution(
            QueryString=sql, WorkGroup=WORKGROUP, QueryExecutionContext={"Database": database}
        )["QueryExecutionId"]
        while True:
            status = self.client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
            if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(1)
        if status["State"] != "SUCCEEDED":
            raise RuntimeError(f"Athena query failed: {status.get('StateChangeReason')}\n{sql}")
        if not fetch:
            return []
        rows: list[list[str | None]] = []
        token = None
        while True:
            page = self.client.get_query_results(QueryExecutionId=query_id, **({"NextToken": token} if token else {}))
            rows += [[c.get("VarCharValue") for c in row["Data"]] for row in page["ResultSet"]["Rows"]]
            token = page.get("NextToken")
            if not token:
                return rows[1:]


def ensure_bucket(region: str, bucket: str) -> None:
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": region})
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration=dict.fromkeys(
                ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"), True
            ),
        )
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    s3.upload_file(str(config.DATA_DIR / "cells_pop.parquet"), bucket, "raw/cells/cells.parquet")


def ensure_workgroup(region: str, bucket: str) -> None:
    client = boto3.client("athena", region_name=region)
    try:
        client.create_work_group(
            Name=WORKGROUP,
            Configuration={
                "ResultConfiguration": {"OutputLocation": f"s3://{bucket}/athena-results/"},
                "EnforceWorkGroupConfiguration": True,
            },
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "InvalidRequestException":
            raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="eu-central-1")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    account = boto3.client("sts", region_name=args.region).get_caller_identity()["Account"]
    bucket = f"isolated-italy-lake-{account}"
    ensure_bucket(args.region, bucket)
    ensure_workgroup(args.region, bucket)

    athena = Athena(args.region)
    athena.run(f"CREATE DATABASE IF NOT EXISTS {DATABASE}", database="default")
    athena.run("DROP TABLE IF EXISTS cells_raw")
    athena.run(f"""
        CREATE EXTERNAL TABLE cells_raw (
          cell string, n bigint, lat double, lon double, prov string, region string, comune string,
          d_grocery float, d_health float, d_pharmacy float, d_phov float, d_phreg float, d_post float,
          d_school float, d_train float, pop bigint)
        STORED AS PARQUET LOCATION 's3://{bucket}/raw/cells/'""")
    athena.run("DROP TABLE IF EXISTS cells")
    far = " + ".join(f"CASE WHEN d_{c} > {config.THRESHOLD_KM} THEN 1 ELSE 0 END" for c in config.ESSENTIAL)
    athena.run(f"""
        CREATE TABLE cells WITH (table_type = 'ICEBERG', location = 's3://{bucket}/iceberg/cells/', is_external = false,
                                 format = 'PARQUET', partitioning = ARRAY['region']) AS
        SELECT *, ({far}) AS nfar FROM cells_raw""")

    total, far1, far3, far5 = athena.run(
        """
        SELECT sum(pop), sum(CASE WHEN nfar >= 1 THEN pop END), sum(CASE WHEN nfar >= 3 THEN pop END),
               sum(CASE WHEN nfar = 5 THEN pop END) FROM cells WHERE pop > 0""",
        fetch=True,
    )[0]
    from_athena = {"total": int(total), "far1": int(far1), "far3": int(far3), "far5": int(far5)}
    from_duckdb = json.loads((config.WEB_DATA_DIR / "headline.json").read_text())
    for key, value in from_athena.items():
        if value != from_duckdb[key]:
            sys.exit(f"mismatch on {key}: Athena {value}, DuckDB {from_duckdb[key]}")
    log.info("Athena and DuckDB agree: %s", from_athena)

    snapshots = athena.run(
        'SELECT snapshot_id, operation, committed_at FROM "cells$snapshots" ORDER BY committed_at', fetch=True
    )
    files, size = athena.run('SELECT count(*), sum(file_size_in_bytes) FROM "cells$files"', fetch=True)[0]
    info = {
        "engine": "Amazon Athena v3 on Apache Iceberg",
        "table": f"{DATABASE}.cells",
        "snapshots": snapshots,
        "data_files": int(files),
        "bytes": int(size),
        "agree_with_duckdb": True,
        "headline": from_athena,
    }
    (config.WEB_DATA_DIR / "lakehouse.json").write_text(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
