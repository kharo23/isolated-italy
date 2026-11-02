import json
from unittest import mock

import pytest
from botocore.exceptions import ClientError

import reach


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setenv("CACHE_BUCKET", "bucket")
    monkeypatch.setenv("CAP_TABLE", "table")
    monkeypatch.setenv("DAILY_CAP", "10")


def client_error(code, message=""):
    return ClientError({"Error": {"Code": code, "Message": message}}, "op")


def test_parse_point_accepts_italy_and_rounds():
    assert reach.parse_point("10.123456789,44.4032") == (10.12346, 44.4032)


@pytest.mark.parametrize("text", ["2.35,48.85", "abc,1", "10", ""])
def test_parse_point_rejects_bad_input(text):
    with pytest.raises(reach.BadRequest):
        reach.parse_point(text)


def test_parse_request_clamps_minutes_and_drops_far_destinations():
    params = {"lon": "10.0", "lat": "44.0", "min": "999", "pharmacy": "10.05,44.02", "health": "16.0,40.0"}
    origin, minutes, destinations = reach.parse_request(params)
    assert origin == (10.0, 44.0)
    assert minutes == reach.MAX_MINUTES
    assert list(destinations) == ["pharmacy"]


def test_cache_key_groups_nearby_origins():
    a = reach.cache_key((10.12001, 44.40001), 15, {"pharmacy": (10.2, 44.4)})
    b = reach.cache_key((10.12049, 44.40049), 15, {"pharmacy": (10.2, 44.4)})
    c = reach.cache_key((10.2, 44.5), 15, {"pharmacy": (10.2, 44.4)})
    assert a == b != c


def test_handler_rejects_invalid_request():
    result = reach.handler({"queryStringParameters": {"lon": "2.35", "lat": "48.85"}})
    assert result["statusCode"] == 400


def test_handler_serves_from_cache_without_budget():
    with (
        mock.patch.object(reach, "read_cache", return_value='{"cached":true}'),
        mock.patch.object(reach, "take_budget") as budget,
    ):
        result = reach.handler({"queryStringParameters": {"lon": "10.1", "lat": "44.4"}})
    assert result["statusCode"] == 200
    assert result["headers"]["x-cache"] == "hit"
    budget.assert_not_called()


def test_handler_returns_429_when_budget_is_exhausted():
    with (
        mock.patch.object(reach, "read_cache", return_value=None),
        mock.patch.object(reach, "take_budget", return_value=False),
    ):
        result = reach.handler({"queryStringParameters": {"lon": "10.1", "lat": "44.4"}})
    assert result["statusCode"] == 429
    assert json.loads(result["body"]) == {"error": "daily_cap_reached"}


def test_handler_maps_unroutable_origin_to_422():
    routes = mock.Mock()
    routes.calculate_isolines.side_effect = client_error(
        "ValidationException", "'Origin' could not be matched to the route network"
    )
    with (
        mock.patch.object(reach, "read_cache", return_value=None),
        mock.patch.object(reach, "take_budget", return_value=True),
        mock.patch.object(reach, "client", return_value=routes),
    ):
        result = reach.handler({"queryStringParameters": {"lon": "11.5", "lat": "40.0"}})
    assert result["statusCode"] == 422
    assert json.loads(result["body"]) == {"error": "no_road"}


def test_handler_does_not_cache_when_a_route_is_throttled():
    routes = mock.Mock()
    routes.calculate_isolines.return_value = {
        "Isolines": [{"Geometries": [{"Polygon": [[[10, 44], [10.1, 44], [10.1, 44.1], [10, 44]]]}]}]
    }
    routes.calculate_routes.side_effect = client_error("ThrottlingException")
    with (
        mock.patch.object(reach, "read_cache", return_value=None),
        mock.patch.object(reach, "take_budget", return_value=True),
        mock.patch.object(reach, "write_cache") as write,
        mock.patch.object(reach, "client", return_value=routes),
    ):
        result = reach.handler({"queryStringParameters": {"lon": "10.05", "lat": "44.02", "pharmacy": "10.06,44.03"}})
    assert result["statusCode"] == 502
    write.assert_not_called()


def test_handler_success_caches_and_reports_routes():
    routes = mock.Mock()
    routes.calculate_isolines.return_value = {
        "Isolines": [{"Geometries": [{"Polygon": [[[10, 44], [10.1, 44], [10.1, 44.1], [10, 44]]]}]}]
    }
    routes.calculate_routes.return_value = {"Routes": [{"Summary": {"Duration": 900, "Distance": 10913}}]}
    with (
        mock.patch.object(reach, "read_cache", return_value=None),
        mock.patch.object(reach, "take_budget", return_value=True),
        mock.patch.object(reach, "write_cache") as write,
        mock.patch.object(reach, "client", return_value=routes),
    ):
        result = reach.handler({"queryStringParameters": {"lon": "10.05", "lat": "44.02", "pharmacy": "10.06,44.03"}})
    body = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert body["routes"]["pharmacy"] == {"minutes": 15.0, "km": 10.913}
    assert body["isoline"]["type"] == "MultiPolygon"
    write.assert_called_once()
