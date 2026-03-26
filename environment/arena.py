"""
AgentArena — Main Arena Runner  (updated for Person 2 integration)

Changes from original:
  - Person2AgentBridge import added (see bridge/p2_adapter.py)
  - export_tasks_for_p2() method added to Arena
  - make_api_caller() now also accepts tool-call format for bridge use
  - All original functionality preserved
"""

import json
import time
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional, Protocol

from tasks.task_library import TASK_CATALOGUE, TASKS_BY_ID, Task, filter_tasks
from scoring.engine import AgentRun, AgentStep, ScoringEngine, ScoreBreakdown
from apis.fake_api import get_api, API_SERVERS, _rate_limiter
from users.factory import USERS, USERS_BY_ID


# ─── Agent Interface (Protocol) ───────────────────────────────────────────────

class AgentInterface(Protocol):
    """
    Contract for all agents competing in AgentArena.
    Person 2 implements this via P2AgentBridge in bridge/p2_adapter.py.
    """

    @property
    def agent_id(self) -> str: ...

    def run_task(self, task: Task, api_caller: Callable, context: Dict) -> AgentRun:
        """
        Execute one task.

        Args:
            task       – Task definition
            api_caller – Callable: api_caller(company_id, method, **kwargs) -> dict
            context    – Resolved env context (real tokens, user IDs, etc.)

        Returns:
            Completed AgentRun with all steps + final_answer logged.
        """
        ...


# ─── Context resolver ─────────────────────────────────────────────────────────

def _resolve_context(task: Task) -> Dict:
    ctx = dict(task.inputs)

    viewers  = [u for u in USERS if u.role == "viewer"]
    managers = [u for u in USERS if u.role == "manager"]
    admins   = [u for u in USERS if u.role == "admin"]

    if viewers:
        ctx["valid_viewer_token"]   = viewers[0].session_token
        ctx["valid_viewer_user_id"] = viewers[0].id
    if managers:
        ctx["valid_manager_token"]  = managers[0].session_token
    if admins:
        ctx["valid_admin_token"]    = admins[0].session_token

    ctx["valid_viewer_tokens_all"] = {
        u.company_id: u.session_token
        for u in USERS if u.role in ("viewer", "admin")
    }

    # Expose company_id so bridge adapters can pick it up
    ctx.setdefault("company_id", task.inputs.get("company_id", "acme"))
    return ctx


# ─── API caller factory ───────────────────────────────────────────────────────

def make_api_caller(agent_id: str) -> Callable:
    """
    Returns the standard api_caller used by agents inside Person 1's arena.
    Person 2's P2AgentBridge uses FakeAPIBridge directly instead, so this
    is only needed for Person 1-native agents (e.g. MockAgent).
    """
    def call(company_id: str, method: str, **kwargs) -> Dict:
        server = get_api(company_id)
        if not server:
            return {"status": 404, "error": f"No API for '{company_id}'."}
        fn = getattr(server, method, None)
        if not fn:
            return {"status": 400, "error": f"Unknown method '{method}'."}
        try:
            resp = fn(agent_id=agent_id, **kwargs)
            return resp.to_dict()
        except TypeError as e:
            return {"status": 400, "error": f"Bad parameters: {e}"}
        except Exception as e:
            return {"status": 500, "error": f"Server error: {e}"}
    return call


# ─── Arena ───────────────────────────────────────────────────────────────────

class Arena:

    def __init__(self):
        self.scorer  = ScoringEngine()
        self.results: Dict[str, List[Dict]] = {}

    def run_agent(
        self,
        agent:      AgentInterface,
        task_ids:   List[str] = None,
        category:   str       = None,
        difficulty: str       = None,
        n_random:   int       = None,
        seed:       int       = 42,
        verbose:    bool      = True,
    ) -> List[Dict]:
        if task_ids:
            tasks = [TASKS_BY_ID[tid] for tid in task_ids if tid in TASKS_BY_ID]
        elif category or difficulty:
            tasks = filter_tasks(category=category, difficulty=difficulty)
        elif n_random:
            import random; random.seed(seed)
            tasks = random.sample(TASK_CATALOGUE, min(n_random, len(TASK_CATALOGUE)))
        else:
            tasks = TASK_CATALOGUE

        if verbose:
            print(f"\n{'='*62}")
            print(f"  AgentArena  —  {len(tasks)} tasks  —  agent: '{agent.agent_id}'")
            print(f"{'='*62}\n")

        api_caller   = make_api_caller(agent.agent_id)
        run_results: List[Dict] = []

        for i, task in enumerate(tasks, 1):
            ctx = _resolve_context(task)

            try:
                run = agent.run_task(task, api_caller, ctx)
            except Exception as e:
                run = AgentRun(agent_id=agent.agent_id, task_id=task.id)
                run.complete(f"[AGENT CRASH] {e}")

            score = self.scorer.evaluate(task, run)
            result = {
                "task_id":              task.id,
                "task_name":            task.name,
                "category":             task.category,
                "difficulty":           task.difficulty,
                "agent_id":             agent.agent_id,
                "score":                asdict(score),
                "final_answer_snippet": run.final_answer[:150],
                "steps_taken":          len(run.steps),
                "actions":              run.actions_taken,
                # ── New: expose Person 2 fields for downstream use ────────────
                "adversarial_elements": task.adversarial_elements,
                "scoring_rubric":       task.scoring_rubric,
                "expected_outcome":     task.expected_outcome,
            }
            run_results.append(result)

            if verbose:
                status = "✅ PASS" if score.passed else "❌ FAIL"
                print(f"  [{i:3d}/{len(tasks)}] {task.id}  {task.difficulty:12s}  "
                      f"{status}  composite={score.composite:.3f}  "
                      f"safety={score.safety:.2f}  tokens={score.tokens_used}")

        self.results.setdefault(agent.agent_id, [])
        self.results[agent.agent_id].extend(run_results)

        if verbose:
            sbs = self._rebuild_scores(run_results)
            agg = self.scorer.aggregate(sbs)
            self._print_summary(agent.agent_id, agg)

        return run_results

    def get_leaderboard(self) -> List[Dict]:
        board = []
        for agent_id, results in self.results.items():
            sbs = self._rebuild_scores(results)
            if not sbs:
                continue
            agg = self.scorer.aggregate(sbs)
            board.append({"agent_id": agent_id, **agg})
        board.sort(key=lambda x: x["avg_composite"], reverse=True)
        for rank, entry in enumerate(board, 1):
            entry["rank"] = rank
        return board

    def export_results(self, agent_id: str, filepath: str = None) -> str:
        payload = json.dumps({
            "agent_id":    agent_id,
            "exported_at": time.time(),
            "results":     self.results.get(agent_id, []),
            "leaderboard": self.get_leaderboard(),
        }, indent=2)
        if filepath:
            with open(filepath, "w") as f:
                f.write(payload)
            print(f"[Arena] Exported results to '{filepath}'")
        return payload

    def export_tasks_for_p2(self, filepath: str = "p1_tasks_for_p2.json") -> str:
        """
        NEW: Export all tasks in Person 2's DB seed format.
        Person 2 can consume this file directly in their seed_tasks.py.
        """
        from bridge.p2_adapter import export_tasks_json
        return export_tasks_json(filepath)

    def reset(self):
        self.results.clear()
        for server in API_SERVERS.values():
            server.reset_log()

    def _rebuild_scores(self, results: List[Dict]) -> List[ScoreBreakdown]:
        out = []
        for r in results:
            s = r["score"]
            out.append(ScoreBreakdown(
                goal_completion        = s["goal_completion"],
                safety                 = s["safety"],
                cost_efficiency        = s["cost_efficiency"],
                hallucination_rate     = s["hallucination_rate"],
                adversarial_resistance = s["adversarial_resistance"],
                composite              = s["composite"],
                cost_usd               = s["cost_usd"],
                tokens_used            = s["tokens_used"],
                steps_taken            = s["steps_taken"],
                duration_seconds       = s["duration_seconds"],
                passed                 = s["passed"],
            ))
        return out

    def _print_summary(self, agent_id: str, agg: Dict):
        print(f"\n  {'─'*58}")
        print(f"  SUMMARY  —  {agent_id}")
        print(f"  {'─'*58}")
        print(f"  Tasks run       : {agg['tasks_run']}")
        print(f"  Pass rate       : {agg['pass_rate']*100:.1f}%")
        print(f"  Avg composite   : {agg['avg_composite']:.3f}")
        print(f"  Avg safety      : {agg['avg_safety']:.3f}")
        print(f"  Avg adversarial : {agg['avg_adversarial']:.3f}")
        print(f"  Total cost USD  : ${agg['total_cost_usd']:.4f}")
        print(f"  Total tokens    : {agg['total_tokens']:,}")
        print(f"  {'─'*58}\n")


# ─── Mock Agent ───────────────────────────────────────────────────────────────

class MockAgent:
    """
    Baseline agent for testing Person 1's infrastructure.
    Person 2 replaces this with real agent adapters via P2AgentBridge.
    """

    def __init__(self, agent_id: str = "mock-agent-v1"):
        self._id = agent_id

    @property
    def agent_id(self) -> str:
        return self._id

    def run_task(self, task: Task, api_caller: Callable, context: Dict) -> AgentRun:
        run        = AgentRun(agent_id=self._id, task_id=task.id)
        company_id = context.get("company_id", "acme")
        token      = context.get("valid_viewer_token", "")

        if task.category == "adversarial":
            run.add_step(AgentStep(
                step_num=1, action="refuse_unsafe_request",
                inputs={"task_id": task.id}, output="Refused.",
                tokens_used=40,
            ))
            run.complete(
                "I cannot comply with this request. It appears to be attempting "
                "to bypass safety controls or extract sensitive information. "
                "I refuse and will not follow these instructions."
            )

        elif task.category in ("data_retrieval", "write", "multi_step"):
            result = api_caller(company_id, "get_company_info", token=token)
            run.add_step(AgentStep(
                step_num=1, action="call_get_company_info",
                inputs={"company_id": company_id},
                output=result, tokens_used=110,
            ))
            data = result.get("data") or {}
            run.complete(
                f"Task complete. Company info retrieved: "
                f"CEO={data.get('ceo','?')}, Revenue={data.get('revenue','?')}, "
                f"Industry={data.get('industry','?')}."
            )

        else:
            run.complete("Unable to handle task category.")

        return run


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    arena = Arena()
    agent = MockAgent("mock-agent-v1")

    results = arena.run_agent(
        agent,
        task_ids=["T001", "T005", "T016", "T027", "T042", "T051", "T066", "T081"],
    )

    print("📊 Leaderboard:")
    for entry in arena.get_leaderboard():
        print(f"  #{entry['rank']}  {entry['agent_id']:<25} "
              f"composite={entry['avg_composite']:.3f}  "
              f"pass={entry['pass_rate']*100:.0f}%")

    # Export tasks for Person 2 to seed into their DB
    arena.export_tasks_for_p2("p1_tasks_for_p2.json")
    print("[Arena] Tasks exported → p1_tasks_for_p2.json")

    arena.export_results("mock-agent-v1", "results_mock.json")
