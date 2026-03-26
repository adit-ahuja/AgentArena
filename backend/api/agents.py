from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

import models
import schemas
from db.database import get_db

router = APIRouter()


@router.post("/", response_model=schemas.AgentOut, status_code=201)
def submit_agent(payload: schemas.AgentSubmit, db: Session = Depends(get_db)):
    """Submit a new agent to AgentArena."""
    agent = models.Agent(
        name=payload.name,
        description=payload.description,
        agent_type=payload.agent_type,
        model_backbone=payload.model_backbone,
        docker_image=payload.docker_image,
        api_endpoint=payload.api_endpoint,
        config=payload.config,
        version=payload.version,
        submitter_email=payload.submitter_email,
        status=models.AgentStatus.active,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/", response_model=List[schemas.AgentOut])
def list_agents(
    skip: int = 0,
    limit: int = 50,
    agent_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Agent).filter(
        models.Agent.status == models.AgentStatus.active
    )
    if agent_type:
        query = query.filter(models.Agent.agent_type == agent_type)
    return query.offset(skip).limit(limit).all()


@router.get("/{agent_id}", response_model=schemas.AgentOut)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{agent_id}/scores", response_model=List[schemas.AgentScoreOut])
def get_agent_scores(agent_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.AgentScore)
        .filter(models.AgentScore.agent_id == agent_id)
        .order_by(models.AgentScore.created_at.desc())
        .all()
    )


@router.get("/{agent_id}/runs", response_model=List[schemas.RunOut])
def get_agent_runs(agent_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.Run)
        .filter(models.Run.agent_id == agent_id)
        .order_by(models.Run.created_at.desc())
        .all()
    )


@router.get("/{agent_id}/fingerprint")
def get_behavioral_fingerprint(agent_id: str, db: Session = Depends(get_db)):
    """Return the behavioral fingerprint for an agent."""
    from engine.failure_analyzer import FailureAnalyzer

    task_results = (
        db.query(models.TaskResult)
        .join(models.Run)
        .filter(models.Run.agent_id == agent_id)
        .all()
    )
    serialized = [
        {
            "tokens_used":  r.tokens_used,
            "time_seconds": r.time_seconds,
            "status":       r.status,
            "trace":        r.trace or [],
        }
        for r in task_results
    ]
    return FailureAnalyzer.behavioral_fingerprint(serialized)


@router.get("/{agent_id}/elo-history")
def get_elo_history(agent_id: str, db: Session = Depends(get_db)):
    history = (
        db.query(models.EloHistory)
        .filter(models.EloHistory.agent_id == agent_id)
        .order_by(models.EloHistory.created_at.asc())
        .all()
    )
    return [
        {
            "run_id":     h.run_id,
            "elo_before": h.elo_before,
            "elo_after":  h.elo_after,
            "delta":      h.delta,
            "created_at": h.created_at,
        }
        for h in history
    ]
