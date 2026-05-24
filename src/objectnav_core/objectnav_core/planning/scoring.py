from __future__ import annotations


def score_frontier_candidate(
    information_gain: float,
    path_cost: float,
    revisit_penalty: float,
) -> float:
    return information_gain - path_cost - revisit_penalty

