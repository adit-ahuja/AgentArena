"""
AgentArena Benchmarking Engine
Orchestrates task runs, scoring, Elo updates, and failure analysis.
"""

import asyncio
import time
import json
from typing import List, Optional, Callable
from datetime import datetime

from sqlalchemy.orm import Session

import models
from agents.base import TaskContext
from agents.custom_adapter import build_adapter
from engine.scorer import Scorer
from engine.elo import EloEngine
from engine.failure_analyzer import FailureAnalyzer
from settings import get_settings

settings = get_settings()


class BenchmarkEngine:
    def __init__(
        self,
        db: Session,
        on_progress: Optional[Callable] = None,  # callback for WebSocket streaming
    ):
        self.db             = db
        self.on_progress    = on_progress
        self.scorer         = Scorer()
        self.elo            = EloEngine()
        self.analyzer       = FailureAnalyzer(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
        )

    # ── Main Entry Point ──────────────────────────────────────────────────────

    async def run_benchmark(self, run_id: str) -> None:
        """
        Execute a full benchmark run.
        Called async — updates DB as each task completes.
        """
        run: models.Run = self.db.query(models.Run).filter(
            models.Run.id == run_id
        ).first()

        if not run:
            raise ValueError(f"Run {run_id} not found")

        agent: models.Agent = self.db.query(models.Agent).filter(
            models.Agent.id == run.agent_id
        ).first()

        # ── Load tasks ────────────────────────────────────────────────────────
        tasks = self._load_tasks(run)

        run.status      = models.RunStatus.running
        run.started_at  = datetime.utcnow()
        run.total_tasks = len(tasks)
        self.db.commit()

        await self._emit("run_started", {
            "run_id": run_id, "total_tasks": len(tasks)
        })

        # ── Build agent adapter ───────────────────────────────────────────────
        try:
            adapter = build_adapter(agent.agent_type, agent.config)
        except Exception as e:
            run.status = models.RunStatus.failed
            run.error  = str(e)
            self.db.commit()
            return

        # ── Run tasks (with concurrency limit) ────────────────────────────────
        all_scores     = []
        total_tokens   = 0
        total_cost     = 0.0
        wall_start     = time.time()

        semaphore = asyncio.Semaphore(3)   # max 3 concurrent task runs

        async def run_one_task(task_row: models.Task):
            async with semaphore:
                return await self._run_single_task(
                    run, agent, adapter, task_row
                )

        results = await asyncio.gather(
            *[run_one_task(t) for t in tasks],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                continue
            if result:
                all_scores.append(result["aas"])
                total_tokens += result["tokens_used"]
                total_cost   += result["cost_usd"]
                run.completed_tasks += 1
                self.db.commit()

        # ── Finalize run ──────────────────────────────────────────────────────
        run.wall_time_secs = time.time() - wall_start
        run.total_tokens   = total_tokens
        run.total_cost_usd = total_cost
        run.status         = models.RunStatus.completed
        run.finished_at    = datetime.utcnow()
        self.db.commit()

        # ── Compute aggregate score & update Elo ─────────────────────────────
        if all_scores:
            avg_aas = sum(all_scores) / len(all_scores)
            await self._save_aggregate_score(run, agent, all_scores, avg_aas)
            await self._update_elo(agent, avg_aas)

        await self._emit("run_completed", {
            "run_id": run_id,
            "aas":    round(sum(all_scores) / len(all_scores), 2) if all_scores else 0,
        })

    # ── Single Task Execution ─────────────────────────────────────────────────

    async def _run_single_task(
        self,
        run:       models.Run,
        agent:     models.Agent,
        adapter,
        task_row:  models.Task,
    ) -> Optional[dict]:
        """Run the agent on one task and persist the result."""

        # ── Hydrate environment with live FakeAPI data ──────────────────────────
        try:
            import sys, os
            env_path = os.environ.get("ENV_PATH", os.path.join(os.path.dirname(__file__), "../../environment"))
            if env_path not in sys.path:
                sys.path.insert(0, env_path)
            from bridge.p2_adapter import FakeAPIBridge
            from users.factory import USERS
            company_id = (task_row.environment or {}).get("data", {}).get("company_id", "acme")
            viewer = next((u for u in USERS if u.role in ("admin","viewer") and u.company_id == company_id), None)
            token  = viewer.session_token if viewer else ""
            bridge = FakeAPIBridge(agent_id=agent.id, token=token)
            tools  = []
            for tool in (task_row.environment or {}).get("tools", []):
                t = dict(tool)
                if not t.get("response"):
                    resp = bridge.call(company_id, t["name"], {})
                    t["response"] = resp.get("data") or {}
                tools.append(t)
            live_env = {**(task_row.environment or {}), "tools": tools, "data": {"company_id": company_id}}
        except Exception:
            live_env = task_row.environment or {}

        task_ctx = TaskContext(
            task_id=task_row.id,
            title=task_row.title,
            prompt=task_row.prompt,
            environment=live_env,
            max_tokens=task_row.max_tokens,
            timeout_seconds=task_row.timeout_seconds,
            adversarial_elements=task_row.adversarial_elements or [],
        )

        await self._emit("task_started", {
            "run_id": run.id, "task_id": task_row.id, "title": task_row.title
        })

        # ── Execute with timeout ──────────────────────────────────────────────
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, adapter.run, task_ctx),
                timeout=task_row.timeout_seconds + 5,
            )
        except asyncio.TimeoutError:
            from agents.base import AgentResult
            result = AgentResult(
                final_answer="",
                trace=[],
                tokens_used=0,
                time_seconds=task_row.timeout_seconds,
                cost_usd=0.0,
                success=False,
                error="Task timeout exceeded",
            )

        # ── Score the result ──────────────────────────────────────────────────
        task_score = self.scorer.score_task(result, task_ctx, task_row)

        scores_dict = {
            "goal_completion": task_score.goal_completion,
            "hallucination":   task_score.hallucination,
            "safety":          task_score.safety,
            "adversarial":     task_score.adversarial,
            "cost":            task_score.cost,
            "aas":             task_score.aas,
        }

        # ── AI failure analysis ───────────────────────────────────────────────
        ai_analysis = None
        if task_score.status in ("fail", "partial"):
            try:
                ai_analysis = await self.analyzer.analyze(
                    result, task_ctx, scores_dict
                )
            except Exception:
                ai_analysis = self.analyzer._rule_based_analysis(
                    result, task_ctx, scores_dict
                )

        # ── Persist TaskResult ────────────────────────────────────────────────
        trace_serializable = [
            {
                "step":      s.step,
                "action":    s.action,
                "tool":      s.tool,
                "input":     str(s.input)[:500]  if s.input  else None,
                "output":    str(s.output)[:500] if s.output else None,
                "timestamp": s.timestamp,
                "tokens":    s.tokens,
                "error":     s.error,
            }
            for s in result.trace
        ]

        task_result = models.TaskResult(
            run_id=run.id,
            task_id=task_row.id,
            status=task_score.status,
            agent_output=result.final_answer[:2000] if result.final_answer else None,
            trace=trace_serializable,
            tokens_used=result.tokens_used,
            time_seconds=result.time_seconds,
            goal_completion_score=task_score.goal_completion,
            hallucination_score=task_score.hallucination,
            safety_score=task_score.safety,
            adversarial_score=task_score.adversarial,
            cost_score=task_score.cost,
            failure_reasons=task_score.failure_reasons,
            ai_analysis=ai_analysis,
        )
        self.db.add(task_result)
        self.db.commit()

        await self._emit("task_completed", {
            "run_id":  run.id,
            "task_id": task_row.id,
            "status":  task_score.status,
            "aas":     task_score.aas,
        })

        return {
            "aas":        task_score.aas,
            "tokens_used": result.tokens_used,
            "cost_usd":   result.cost_usd,
        }

    # ── Aggregate Score ───────────────────────────────────────────────────────

    async def _save_aggregate_score(
        self,
        run:        models.Run,
        agent:      models.Agent,
        all_aas:    List[float],
        avg_aas:    float,
    ):
        """Compute per-dimension averages and save to agent_scores."""
        task_results = (
            self.db.query(models.TaskResult)
            .filter(models.TaskResult.run_id == run.id)
            .all()
        )

        def avg(field: str) -> float:
            vals = [getattr(r, field) for r in task_results if getattr(r, field) is not None]
            return round(sum(vals) / len(vals), 2) if vals else 0.0

        pass_count = sum(1 for r in task_results if r.status == "pass")
        pass_rate  = pass_count / len(task_results) if task_results else 0.0

        ci_low, ci_high = self.scorer.compute_confidence_interval(all_aas)

        score = models.AgentScore(
            agent_id=agent.id,
            run_id=run.id,
            aas_score=round(avg_aas, 2),
            goal_completion_avg=avg("goal_completion_score"),
            hallucination_avg=avg("hallucination_score"),
            safety_avg=avg("safety_score"),
            adversarial_avg=avg("adversarial_score"),
            cost_avg=avg("cost_score"),
            pass_rate=round(pass_rate * 100, 2),
            elo_before=agent.elo_rating,
            confidence_interval_low=ci_low,
            confidence_interval_high=ci_high,
        )
        self.db.add(score)
        self.db.commit()

    # ── Elo Update ────────────────────────────────────────────────────────────

    async def _update_elo(self, agent: models.Agent, agent_aas: float):
        """Fetch peer agents and update Elo ratings."""
        # Get all other agents that have scores
        peer_scores = (
            self.db.query(models.AgentScore)
            .filter(models.AgentScore.agent_id != agent.id)
            .order_by(models.AgentScore.created_at.desc())
            .limit(50)
            .all()
        )

        if not peer_scores:
            return

        peer_ratings = []
        peer_aas_list = []
        for ps in peer_scores:
            peer_agent = self.db.query(models.Agent).filter(
                models.Agent.id == ps.agent_id
            ).first()
            if peer_agent:
                peer_ratings.append(peer_agent.elo_rating)
                peer_aas_list.append(ps.aas_score)

        new_rating, delta = self.elo.update_from_benchmark(
            agent_rating=agent.elo_rating,
            agent_aas=agent_aas,
            peer_ratings=peer_ratings,
            peer_aas_scores=peer_aas_list,
        )

        # Update agent Elo
        old_rating    = agent.elo_rating
        agent.elo_rating = new_rating
        self.db.commit()

        # Update score record
        score = (
            self.db.query(models.AgentScore)
            .filter(models.AgentScore.agent_id == agent.id)
            .order_by(models.AgentScore.created_at.desc())
            .first()
        )
        if score:
            score.elo_before = old_rating
            score.elo_after  = new_rating
            self.db.commit()

        # Log Elo history
        elo_entry = models.EloHistory(
            agent_id=agent.id,
            run_id=score.run_id if score else "",
            elo_before=old_rating,
            elo_after=new_rating,
            delta=delta,
        )
        self.db.add(elo_entry)
        self.db.commit()

    # ── Task Loading ──────────────────────────────────────────────────────────

    def _load_tasks(self, run: models.Run) -> List[models.Task]:
        """Load tasks based on the run's task_suite setting."""
        base_query = self.db.query(models.Task)

        if run.task_suite == "full":
            return base_query.all()
        elif run.task_suite == "quick":
            return base_query.limit(10).all()
        elif run.task_suite == "adversarial":
            return base_query.filter(
                models.Task.category == models.TaskCategory.adversarial
            ).all()
        elif run.task_ids:
            return base_query.filter(models.Task.id.in_(run.task_ids)).all()
        else:
            return base_query.all()

    # ── WebSocket Progress Emitter ────────────────────────────────────────────

    async def _emit(self, event: str, data: dict):
        if self.on_progress:
            try:
                await self.on_progress(event, data)
            except Exception:
                pass
