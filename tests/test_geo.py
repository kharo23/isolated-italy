import numpy as np
import pytest

from isolated_italy.geo import chord_from_km, km_from_chord, nearest_km, unit_vectors


def test_chord_round_trip():
    for km in (0.5, 5.0, 120.0, 1500.0):
        assert km_from_chord(chord_from_km(km)) == pytest.approx(km, rel=1e-9)


def test_unit_vectors_are_normalised():
    v = unit_vectors([41.9, 45.46, -33.9], [12.5, 9.19, 151.2])
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0)


def test_nearest_km_matches_haversine():
    # Rome (41.9028, 12.4964) to Milan (45.4642, 9.1900): about 477 km great circle.
    points = np.array([[45.4642, 9.1900]])
    query = unit_vectors([41.9028], [12.4964])
    assert nearest_km(points, query)[0] == pytest.approx(477, abs=3)


def test_nearest_km_picks_closest_point():
    points = np.array([[40.0, 10.0], [44.0, 10.0]])
    query = unit_vectors([43.5], [10.0])
    assert nearest_km(points, query)[0] == pytest.approx(55.6, abs=1.0)
