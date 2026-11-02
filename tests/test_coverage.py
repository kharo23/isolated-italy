import numpy as np

from isolated_italy.coverage import greedy_cover


def test_greedy_cover_prefers_largest_then_marginal_gain():
    # Elements 0..4 with weights; candidate 0 covers {0,1}, 1 covers {1,2}, 2 covers {3}.
    weights = np.array([5, 4, 3, 2, 1])
    neighbours = [[0, 1], [1, 2], [3]]
    picks = greedy_cover(weights, neighbours, top=3)
    assert picks[0] == (0, 9)  # 5 + 4
    assert picks[1] == (1, 3)  # element 1 already covered, only 3 remains
    assert picks[2] == (2, 2)


def test_greedy_cover_respects_top_and_skips_zero_gain():
    weights = np.array([1, 1])
    neighbours = [[0, 1], [0, 1]]
    assert greedy_cover(weights, neighbours, top=5) == [(0, 2)]
