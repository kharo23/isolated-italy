"""Reach API: road routes and a drive-time area for a point in Italy.

GET /api/reach?lon=..&lat=..&min=15&pharmacy=lon,lat&health=lon,lat&school=lon,lat

Response: {"origin": [lon, lat], "minutes": 15, "isoline": <GeoJSON MultiPolygon>,
           "routes": {"pharmacy": {"minutes": .., "km": ..}, ...}}

The function sits in front of Amazon Location Service Routes so that:
  * results are cached in S3 by rounded coordinates, which keeps repeated requests free;
  * a daily counter in DynamoDB caps the number of routing calls;
  * inputs are validated (Italian bounding box, known categories, bounded distances).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import time
from functools import cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

CATEGORIES = ("pharmacy", "health", "school")
ITALY_BBOX = (6.5, 35.3, 18.9, 47.2)  # lon_min, lat_min, lon_max, lat_max
MAX_DESTINATION_KM = 80
MIN_MINUTES, MAX_MINUTES = 5, 30
KM_PER_DEGREE = 111.19


class BadRequest(ValueError):
    """The request parameters are invalid."""


@cache
def client(name: str):
    return boto3.client(name, region_name=os.environ.get("LOCATION_REGION", os.environ.get("AWS_REGION")))


def settings() -> dict[str, Any]:
    return {
        "bucket": os.environ["CACHE_BUCKET"],
        "table": os.environ["CAP_TABLE"],
        "daily_cap": int(os.environ.get("DAILY_CAP", "1000")),
    }


def response(status: int, body: dict, *, extra_headers: dict | None = None) -> dict:
    headers = {"content-type": "application/json", "access-control-allow-origin": "*", **(extra_headers or {})}
    return {"statusCode": status, "headers": headers, "body": json.dumps(body, separators=(",", ":"))}


def parse_point(text: str) -> tuple[float, float]:
    """Parse "lon,lat", require it to lie in Italy, and round to 5 decimals (about 1 m)."""
    try:
        lon, lat = (float(part) for part in text.split(","))
    except (ValueError, AttributeError) as error:
        raise BadRequest("malformed point") from error
    lon_min, lat_min, lon_max, lat_max = ITALY_BBOX
    if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
        raise BadRequest("outside Italy")
    return round(lon, 5), round(lat, 5)


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    scale = math.cos(math.radians(a[1]))
    return math.hypot((a[0] - b[0]) * scale, a[1] - b[1]) * KM_PER_DEGREE


def parse_request(params: dict[str, str]) -> tuple[tuple[float, float], int, dict[str, tuple[float, float]]]:
    """Validate query parameters; destinations farther than MAX_DESTINATION_KM are dropped."""
    try:
        origin = parse_point(f"{params['lon']},{params['lat']}")
        minutes = min(max(int(params.get("min", "15")), MIN_MINUTES), MAX_MINUTES)
    except (KeyError, ValueError) as error:
        raise BadRequest("missing or invalid parameter") from error
    destinations = {c: parse_point(params[c]) for c in CATEGORIES if params.get(c)}
    destinations = {c: d for c, d in destinations.items() if distance_km(origin, d) <= MAX_DESTINATION_KM}
    return origin, minutes, destinations


def cache_key(origin: tuple[float, float], minutes: int, destinations: dict[str, tuple[float, float]]) -> str:
    """Cache key on a ~100 m origin grid plus the exact destinations."""
    payload = [round(origin[0], 3), round(origin[1], 3), minutes, sorted(destinations.items())]
    digest = hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:40]
    return f"reach-cache/{digest}.json"


def take_budget(units: int) -> bool:
    """Atomically add ``units`` to today's counter; False if the daily cap would be exceeded."""
    cfg = settings()
    today = time.strftime("%Y-%m-%d", time.gmtime())
    try:
        client("dynamodb").update_item(
            TableName=cfg["table"],
            Key={"day": {"S": today}},
            UpdateExpression="ADD calls :n SET #ttl = :t",
            ConditionExpression="attribute_not_exists(calls) OR calls <= :max",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={
                ":n": {"N": str(units)},
                ":max": {"N": str(cfg["daily_cap"] - units)},
                ":t": {"N": str(int(time.time()) + 3 * 86400)},
            },
        )
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def read_cache(key: str) -> str | None:
    try:
        return client("s3").get_object(Bucket=settings()["bucket"], Key=key)["Body"].read().decode()
    except ClientError:
        return None


def write_cache(key: str, body: str) -> None:
    """Best effort: a failed write only means the next identical request is computed again."""
    with contextlib.suppress(ClientError):
        client("s3").put_object(
            Bucket=settings()["bucket"], Key=key, Body=body.encode(), ContentType="application/json"
        )


def route_summary(route: dict) -> dict:
    summary = route.get("Summary") or {}
    overview = summary.get("Overview") or summary
    return {"minutes": overview["Duration"] / 60, "km": overview["Distance"] / 1000}


def compute(origin, minutes, destinations) -> dict | tuple[int, dict]:
    """Call Amazon Location. Returns the payload, or (status, error body) if routing is not possible."""
    routes = client("geo-routes")
    try:
        isolines = routes.calculate_isolines(
            Origin=list(origin), Thresholds={"Time": [minutes * 60]}, TravelMode="Car", IsolineGeometryFormat="Simple"
        )
        polygons = [g["Polygon"] for g in isolines["Isolines"][0]["Geometries"] if "Polygon" in g]
    except (IndexError, KeyError):
        return 502, {"error": "routing_unavailable"}
    except ClientError as error:
        if "could not be matched" in error.response["Error"].get("Message", ""):
            return 422, {"error": "no_road"}  # sea, lake, or too far from any road
        return 502, {"error": "routing_unavailable"}

    result: dict[str, Any] = {
        "origin": origin,
        "minutes": minutes,
        "isoline": {"type": "MultiPolygon", "coordinates": polygons},
        "routes": {},
    }
    for category, destination in destinations.items():
        try:
            route = routes.calculate_routes(
                Origin=list(origin), Destination=list(destination), TravelMode="Car", LegGeometryFormat="Simple"
            )["Routes"][0]
            result["routes"][category] = route_summary(route)
        except ClientError as error:
            if error.response["Error"]["Code"] in ("ValidationException", "ResourceNotFoundException"):
                continue  # unroutable destination (island, no road)
            return 502, {"error": "routing_unavailable"}  # throttling and the like: never cache a partial answer
        except (IndexError, KeyError):
            continue
    return result


def handler(event: dict, _context: object = None) -> dict:
    try:
        origin, minutes, destinations = parse_request(event.get("queryStringParameters") or {})
    except BadRequest:
        return response(400, {"error": "bad request"})

    key = cache_key(origin, minutes, destinations)
    cached = read_cache(key)
    if cached is not None:
        return {
            "statusCode": 200,
            "headers": {
                "content-type": "application/json",
                "access-control-allow-origin": "*",
                "x-cache": "hit",
                "cache-control": "public, max-age=86400",
            },
            "body": cached,
        }

    if not take_budget(1):
        return response(429, {"error": "daily_cap_reached"})
    if destinations and not take_budget(len(destinations)):
        destinations = {}
        partial = True
    else:
        partial = False

    outcome = compute(origin, minutes, destinations)
    if isinstance(outcome, tuple):
        status, body = outcome
        return response(status, body)

    body = json.dumps(outcome, separators=(",", ":"))
    if not partial:
        write_cache(key, body)
    headers = {"x-cache": "miss"} if not partial else {}
    if not partial:
        headers["cache-control"] = "public, max-age=86400"
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json", "access-control-allow-origin": "*", **headers},
        "body": body,
    }
