import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

import models
import schemas
from db.database import get_db
from engine.benchmarker import BenchmarkEngine

router = APIRouter()


def _start_benchmark(run_id: str, db: Session):
    """Background task: run the benchmark in an event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    engine = BenchmarkEngine(db=db)
    try:
        loop.run_until_complete(engine.run_benchmark(run_id))
    finally:
        loop.close()


@router.post("/", response_model=schemas.RunOut, status_code=202)
def create_run(
    payload: schemas.RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a new benchmark run for an agent."""
    agent = db.query(models.Agent).filter(
        models.Agent.id == payload.agent_id,
        models.Agent.status == models.AgentStatus.active,
    ).first()

    if not agent:
        raise HTTPException(404, "Agent not found or inactive")

    run = models.Run(
        agent_id=payload.agent_id,
        task_suite=payload.task_suite,
        status=models.RunStatus.queued,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_start_benchmark, run.id, db)
    return run


@router.get("/", response_model=List[schemas.RunOut])
def list_runs(
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(models.Run)
    if agent_id:
        query = query.filter(models.Run.agent_id == agent_id)
    if status:
        query = query.filter(models.Run.status == status)
    return query.order_by(models.Run.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{run_id}", response_model=schemas.RunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/results", response_model=List[schemas.TaskResultOut])
def get_run_results(run_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.TaskResult)
        .filter(models.TaskResult.run_id == run_id)
        .all()
    )


@router.get("/{run_id}/score", response_model=schemas.AgentScoreOut)
def get_run_score(run_id: str, db: Session = Depends(get_db)):
    score = (
        db.query(models.AgentScore)
        .filter(models.AgentScore.run_id == run_id)
        .first()
    )
    if not score:
        raise HTTPException(404, "Score not computed yet")
    return score


@router.get("/{run_id}/summary")
def get_run_summary(run_id: str, db: Session = Depends(get_db)):
    """Rich summary for the run detail page."""
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")

    results = (
        db.query(models.TaskResult)
        .filter(models.TaskResult.run_id == run_id)
        .all()
    )

    score = (
        db.query(models.AgentScore)
        .filter(models.AgentScore.run_id == run_id)
        .first()
    )

    failure_categories = {}
    for r in results:
        for reason in (r.failure_reasons or []):
            key = reason.split("(")[0].strip()
            failure_categories[key] = failure_categories.get(key, 0) + 1

    return {
        "run":               run,
        "score":             score,
        "total_tasks":       run.total_tasks,
        "completed_tasks":   run.completed_tasks,
        "pass_count":        sum(1 for r in results if r.status == "pass"),
        "partial_count":     sum(1 for r in results if r.status == "partial"),
        "fail_count":        sum(1 for r in results if r.status == "fail"),
        "failure_categories": failure_categories,
        "total_cost_usd":    run.total_cost_usd,
        "total_tokens":      run.total_tokens,
        "wall_time_secs":    run.wall_time_secs,
    }
