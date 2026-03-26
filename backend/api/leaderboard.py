from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

import models
import schemas
from db.database import get_db
from engine.elo import EloEngine

router = APIRouter()


def _build_leaderboard_query(db: Session):
    """
    Join agents with their latest scores and compute leaderboard entries.
    Uses a subquery to get each agent's most recent score.
    """
    latest_score_sub = (
        db.query(
            models.AgentScore.agent_id,
            func.max(models.AgentScore.created_at).label("latest")
        )
        .group_by(models.AgentScore.agent_id)
        .subquery()
    )

    rows = (
        db.query(models.Agent, models.AgentScore)
        .join(
            latest_score_sub,
            models.Agent.id == latest_score_sub.c.agent_id
        )
        .join(
            models.AgentScore,
            (models.AgentScore.agent_id == latest_score_sub.c.agent_id) &
            (models.AgentScore.created_at == latest_score_sub.c.latest)
        )
        .filter(models.Agent.status == models.AgentStatus.active)
        .all()
    )

    run_counts = dict(
        db.query(models.Run.agent_id, func.count(models.Run.id))
        .group_by(models.Run.agent_id)
        .all()
    )

    return rows, run_counts


@router.get("/", response_model=List[schemas.LeaderboardEntry])
def get_leaderboard(
    limit:     int    = 50,
    agent_type: Optional[str] = None,
    model:      Optional[str] = None,
    category:   Optional[str] = None,
    db:         Session = Depends(get_db),
):
    """Main leaderboard — sorted by AAS score descending."""
    rows, run_counts = _build_leaderboard_query(db)

    entries = []
    for agent, score in rows:
        if agent_type and agent.agent_type != agent_type:
            continue
        if model and agent.model_backbone != model:
            continue

        entries.append(schemas.LeaderboardEntry(
            rank=0,  # filled below
            agent_id=agent.id,
            agent_name=agent.name,
            agent_type=agent.agent_type,
            model_backbone=agent.model_backbone,
            aas_score=score.aas_score,
            goal_completion=score.goal_completion_avg,
            hallucination=score.hallucination_avg,
            safety=score.safety_avg,
            adversarial=score.adversarial_avg,
            cost=score.cost_avg,
            pass_rate=score.pass_rate,
            elo_rating=agent.elo_rating,
            is_verified=agent.is_verified,
            runs_count=run_counts.get(agent.id, 0),
            confidence_low=score.confidence_interval_low,
            confidence_high=score.confidence_interval_high,
        ))

    entries.sort(key=lambda e: e.aas_score, reverse=True)
    for i, e in enumerate(entries, 1):
        e.rank = i

    return entries[:limit]


@router.post("/rerank", response_model=List[schemas.LeaderboardEntry])
def rerank_leaderboard(
    weights: schemas.ScoringWeights,
    db: Session = Depends(get_db),
):
    """
    Dynamically re-rank the leaderboard with custom scoring weights.
    This is the "drag the slider" feature.
    """
    total = (
        weights.goal_completion +
        weights.hallucination   +
        weights.safety          +
        weights.adversarial     +
        weights.cost
    )
    if abs(total - 1.0) > 0.01:
        # Normalize
        factor = 1.0 / total
        weights.goal_completion *= factor
        weights.hallucination   *= factor
        weights.safety          *= factor
        weights.adversarial     *= factor
        weights.cost            *= factor

    rows, run_counts = _build_leaderboard_query(db)

    entries = []
    for agent, score in rows:
        custom_aas = round(
            score.goal_completion_avg * weights.goal_completion +
            score.hallucination_avg   * weights.hallucination   +
            score.safety_avg          * weights.safety          +
            score.adversarial_avg     * weights.adversarial     +
            score.cost_avg            * weights.cost,
            2
        )
        entries.append(schemas.LeaderboardEntry(
            rank=0,
            agent_id=agent.id,
            agent_name=agent.name,
            agent_type=agent.agent_type,
            model_backbone=agent.model_backbone,
            aas_score=custom_aas,
            goal_completion=score.goal_completion_avg,
            hallucination=score.hallucination_avg,
            safety=score.safety_avg,
            adversarial=score.adversarial_avg,
            cost=score.cost_avg,
            pass_rate=score.pass_rate,
            elo_rating=agent.elo_rating,
            is_verified=agent.is_verified,
            runs_count=run_counts.get(agent.id, 0),
            confidence_low=score.confidence_interval_low,
            confidence_high=score.confidence_interval_high,
        ))

    entries.sort(key=lambda e: e.aas_score, reverse=True)
    for i, e in enumerate(entries, 1):
        e.rank = i

    return entries


@router.get("/compare")
def compare_agents(
    agent_a: str,
    agent_b: str,
    db: Session = Depends(get_db),
):
    """Head-to-head comparison between two agents."""
    def get_latest_score(agent_id: str):
        return (
            db.query(models.AgentScore)
            .filter(models.AgentScore.agent_id == agent_id)
            .order_by(models.AgentScore.created_at.desc())
            .first()
        )

    score_a = get_latest_score(agent_a)
    score_b = get_latest_score(agent_b)

    agent_a_obj = db.query(models.Agent).filter(models.Agent.id == agent_a).first()
    agent_b_obj = db.query(models.Agent).filter(models.Agent.id == agent_b).first()

    if not score_a or not score_b:
        return {"error": "One or both agents have no scores yet"}

    dimensions = ["goal_completion", "hallucination", "safety", "adversarial", "cost"]
    diff = {}
    for dim in dimensions:
        a_val = getattr(score_a, f"{dim}_avg")
        b_val = getattr(score_b, f"{dim}_avg")
        diff[dim] = {
            "agent_a": a_val,
            "agent_b": b_val,
            "delta":   round(a_val - b_val, 2),
            "winner":  "a" if a_val > b_val else ("b" if b_val > a_val else "tie"),
        }

    return {
        "agent_a": {"id": agent_a, "name": agent_a_obj.name if agent_a_obj else agent_a,
                    "aas": score_a.aas_score, "elo": agent_a_obj.elo_rating if agent_a_obj else None},
        "agent_b": {"id": agent_b, "name": agent_b_obj.name if agent_b_obj else agent_b,
                    "aas": score_b.aas_score, "elo": agent_b_obj.elo_rating if agent_b_obj else None},
        "dimensions": diff,
        "overall_winner": "a" if score_a.aas_score > score_b.aas_score else
                          ("b" if score_b.aas_score > score_a.aas_score else "tie"),
    }


@router.get("/elo/top")
def top_elo(limit: int = 10, db: Session = Depends(get_db)):
    """Top agents by Elo rating."""
    agents = (
        db.query(models.Agent)
        .filter(models.Agent.status == models.AgentStatus.active)
        .order_by(models.Agent.elo_rating.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "rank":        i + 1,
            "agent_id":    a.id,
            "name":        a.name,
            "elo_rating":  a.elo_rating,
            "tier":        EloEngine.tier(a.elo_rating),
            "model":       a.model_backbone,
            "is_verified": a.is_verified,
        }
        for i, a in enumerate(agents)
    ]
