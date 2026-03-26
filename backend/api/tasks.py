from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import json

import models
import schemas
from db.database import get_db

router = APIRouter()


@router.get("/", response_model=List[schemas.TaskOut])
def list_tasks(
    category:   Optional[str] = None,
    difficulty: Optional[str] = None,
    skip:       int = 0,
    limit:      int = 100,
    db:         Session = Depends(get_db),
):
    query = db.query(models.Task).filter(models.Task.is_public == True)
    if category:
        query = query.filter(models.Task.category == category)
    if difficulty:
        query = query.filter(models.Task.difficulty == difficulty)
    return query.offset(skip).limit(limit).all()


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(
        models.Task.id == task_id, models.Task.is_public == True
    ).first()
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.get("/{task_id}/stats")
def get_task_stats(task_id: str, db: Session = Depends(get_db)):
    """Per-task performance stats across all agents."""
    results = (
        db.query(models.TaskResult)
        .filter(models.TaskResult.task_id == task_id)
        .all()
    )
    if not results:
        return {"message": "No results for this task yet"}

    pass_rate = sum(1 for r in results if r.status == "pass") / len(results)
    avg_gc    = sum(r.goal_completion_score or 0 for r in results) / len(results)
    avg_time  = sum(r.time_seconds for r in results) / len(results)

    return {
        "task_id":     task_id,
        "total_runs":  len(results),
        "pass_rate":   round(pass_rate * 100, 1),
        "avg_goal_completion": round(avg_gc, 1),
        "avg_time_seconds":    round(avg_time, 1),
        "hardest_for":  "most agents" if pass_rate < 0.3 else "few agents",
    }
