"""
Elo Rating System for AgentArena
Agents gain/lose Elo based on how they perform on shared tasks vs. other agents.
"""

import math
from typing import List, Tuple, Dict
try:
    from settings import get_settings
    _s = get_settings()
    _K_DEFAULT = _s.elo_k_factor
    _R_DEFAULT = _s.elo_initial_rating
except Exception:
    _K_DEFAULT = 32
    _R_DEFAULT = 1200


class EloEngine:
    """
    Classic Elo rating system, adapted for benchmark scoring.

    Instead of head-to-head matches, we treat the 'virtual opponent'
    as the average performance of all other agents on the same task.
    This allows Elo to work in a benchmark (non-game) context.
    """

    def __init__(self, k_factor: int = None, initial_rating: float = None):
        self.k = k_factor or _K_DEFAULT
        self.initial = initial_rating or _R_DEFAULT

    # ── Core Elo Formula ──────────────────────────────────────────────────────

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Expected score of A against B (probability A 'wins')."""
        return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400))

    def new_rating(
        self,
        old_rating: float,
        expected: float,
        actual: float,
    ) -> float:
        """Compute new Elo rating after a match."""
        return old_rating + self.k * (actual - expected)

    # ── Benchmark-Mode Elo ────────────────────────────────────────────────────

    def update_from_benchmark(
        self,
        agent_rating: float,
        agent_aas: float,
        peer_ratings: List[float],
        peer_aas_scores: List[float],
    ) -> Tuple[float, float]:
        """
        Update an agent's Elo based on how it performed vs. all peers
        on the same task suite.

        Returns (new_rating, delta).
        """
        if not peer_ratings:
            return (agent_rating, 0.0)

        total_expected = 0.0
        total_actual   = 0.0

        for peer_r, peer_aas in zip(peer_ratings, peer_aas_scores):
            expected = self.expected_score(agent_rating, peer_r)
            # Actual outcome: 1 if agent beat peer, 0.5 if tie, 0 if lost
            if agent_aas > peer_aas + 2:
                actual = 1.0
            elif abs(agent_aas - peer_aas) <= 2:
                actual = 0.5
            else:
                actual = 0.0

            total_expected += expected
            total_actual   += actual

        n = len(peer_ratings)
        avg_expected = total_expected / n
        avg_actual   = total_actual   / n

        delta      = self.k * (avg_actual - avg_expected)
        new_rating = round(agent_rating + delta, 2)

        return (new_rating, round(delta, 2))

    # ── Leaderboard Rank Utilities ────────────────────────────────────────────

    @staticmethod
    def rank_agents(agents: List[Dict]) -> List[Dict]:
        """
        Sort a list of agent dicts by Elo rating descending.
        Adds 'rank' key to each dict.
        """
        sorted_agents = sorted(agents, key=lambda a: a["elo_rating"], reverse=True)
        for i, agent in enumerate(sorted_agents, start=1):
            agent["rank"] = i
        return sorted_agents

    @staticmethod
    def tier(elo: float) -> str:
        """Human-readable tier label from Elo rating."""
        if elo >= 1800:  return "Champion"
        if elo >= 1600:  return "Expert"
        if elo >= 1400:  return "Advanced"
        if elo >= 1200:  return "Intermediate"
        if elo >= 1000:  return "Beginner"
        return "Unranked"
