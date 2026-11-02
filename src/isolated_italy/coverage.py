"""Greedy maximum-coverage selection."""

from __future__ import annotations

import heapq
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def greedy_cover(weights: NDArray[np.integer], neighbours: Sequence[Sequence[int]], top: int) -> list[tuple[int, int]]:
    """Pick up to ``top`` candidates that cover the largest uncovered weight.

    Candidate ``i`` covers the elements listed in ``neighbours[i]`` (which must include ``i``).
    Uses lazy re-evaluation of marginal gains, so each step is cheap even with many candidates.

    Returns:
        A list of ``(candidate_index, marginal_gain)`` in selection order.
    """
    covered = np.zeros(len(weights), dtype=bool)
    heap = [(-int(weights[list(nb)].sum()), i) for i, nb in enumerate(neighbours)]
    heapq.heapify(heap)
    picks: list[tuple[int, int]] = []
    while heap and len(picks) < top:
        stale_gain, i = heapq.heappop(heap)
        fresh = int(weights[[j for j in neighbours[i] if not covered[j]]].sum())
        if fresh != -stale_gain:
            if fresh > 0:
                heapq.heappush(heap, (-fresh, i))
            continue
        covered[list(neighbours[i])] = True
        picks.append((i, fresh))
    return picks
