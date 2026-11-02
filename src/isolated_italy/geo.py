"""Spherical-geometry helpers built on unit vectors and a KD-tree."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.spatial import cKDTree

from .config import EARTH_RADIUS_KM


def unit_vectors(lat: ArrayLike, lon: ArrayLike) -> NDArray[np.float64]:
    """Convert latitude/longitude in degrees to points on the unit sphere, shape (n, 3)."""
    la = np.radians(np.asarray(lat, dtype=float))
    lo = np.radians(np.asarray(lon, dtype=float))
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def chord_from_km(km: float) -> float:
    """Chord length on the unit sphere for a great-circle distance in kilometres."""
    return 2.0 * np.sin(km / (2.0 * EARTH_RADIUS_KM))


def km_from_chord(chord: ArrayLike) -> NDArray[np.float64]:
    """Great-circle distance in kilometres for chord lengths on the unit sphere."""
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.clip(np.asarray(chord, dtype=float) / 2.0, 0.0, 1.0))


def nearest_km(points_latlon: NDArray[np.float64], queries: NDArray[np.float64]) -> NDArray[np.float64]:
    """Distance in km from each query to the nearest point.

    Args:
        points_latlon: array of shape (n, 2) holding latitude and longitude.
        queries: unit vectors of shape (m, 3), see :func:`unit_vectors`.
    """
    tree = cKDTree(unit_vectors(points_latlon[:, 0], points_latlon[:, 1]))
    chord, _ = tree.query(queries, k=1, workers=-1)
    return km_from_chord(chord)
