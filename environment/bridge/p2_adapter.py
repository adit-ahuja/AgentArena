"""
AgentArena — Person 1 ↔ Person 2 Bridge
========================================

This module is the handshake layer between the two codebases.

What it provides
----------------
1. FakeAPIBridge
   Wraps Person 1's FakeAPIServer so Person 2's adapter can call it
   using Person 2's tool-call format (tool_name + kwargs dict).

2. P2AgentBridge
   Wraps any of Person 2's agent adapters (LangChainAdapter,
   OpenAIAssistantsAdapter, CustomHTTPAdapter …) in Person 1's
   AgentInterface Protocol so they can run inside Person 1's Arena.

3. task_to_db_dict()
   Converts a Person 1 Task object into the dict format Person 2's
   seed_tasks.py (and DB models) expects.

4. seed_p2_db()
   One-call helper: loads all 104 tasks and seeds Person 2's
   PostgreSQL database (via Person 2's SQLAlchemy session).

Usage example
-------------
    # Inside Person 2's seed script:
    from bridge.p2_adapter import seed_p2_db
    from db.database import SessionLocal
    seed_p2_db(SessionLocal())

    # Inside Person 1's arena to run a Person 2 agent:
    from bridge.p2_adapter import P2AgentBridge
    from agents.langchain_adapter import LangChainAdapter
    from arena import Arena

    p2_agent = LangChainAdapter({"llm_type": "openai", "model": "gpt-4o", "api_key": "..."})
    bridge   = P2AgentBridge(agent_id="gpt4o-react-v1", p2_adapter=p2_agent)
    arena    = Arena()
    arena.run_agent(bridge, n_random=20)
"""

import json
import time
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

# ── Person 1 imports ─────────────────────────────────────────────────────────
from tasks.task_library import Task, TASK_CATALOGUE
from scoring.engine import AgentRun, AgentStep
from apis.fake_api import get_api


# ─── 1. FakeAPIBridge ────────────────────────────────────────────────────────

class FakeAPIBridge:
    """
    Translates Person 2's tool-call format into Person 1's FakeAPIServer calls.

    Person 2's environment defines tools with a `_p1_method` key that names
    the FakeAPIServer method to invoke. This bridge reads that key and routes
    the call correctly.

    Usage (inside P2AgentBridge.run_task):
        bridge = FakeAPIBridge(agent_id="my-agent", token="abc-123")
        result = bridge.call("acme", "call_get_company_info", {})
    """

    def __init__(self, agent_id: str, token: str):
        self.agent_id = agent_id
        self.token    = token

    def call(self, company_id: str, tool_name: str, kwargs: Dict) -> Dict:
        """
        Route a tool call from Person 2's adapter to Person 1's FakeAPIServer.

        Args:
            company_id: which company's API to call
            tool_name:  Person 1's action name, e.g. "call_get_company_info"
            kwargs:     additional arguments (e.g. department, status, …)

        Returns:
            dict with "status", "data", "error" — same as FakeAPIServer.to_dict()
        """
        server = get_api(company_id)
        if not server:
            return {"status": 404, "data": None,
                    "error": f"No fake API for company '{company_id}'."}

        # Strip the "call_" prefix to get the FakeAPIServer method name
        method_name = tool_name.replace("call_", "", 1)
        fn = getattr(server, method_name, None)
        if not fn:
            return {"status": 400, "data": None,
                    "error": f"Unknown method '{method_name}' on FakeAPIServer."}

        try:
            resp = fn(agent_id=self.agent_id, token=self.token, **kwargs)
            return resp.to_dict()
        except TypeError as e:
            return {"status": 400, "data": None, "error": f"Bad parameters: {e}"}
        except Exception as e:
            return {"status": 500, "data": None, "error": f"Server error: {e}"}


# ─── 2. P2AgentBridge ────────────────────────────────────────────────────────

class P2AgentBridge:
    """
    Wraps a Person 2 adapter so it satisfies Person 1's AgentInterface Protocol.

    Person 1's Arena calls:
        agent.run_task(task, api_caller, context) -> AgentRun

    This bridge:
        1. Builds a TaskContext (Person 2 format) from Person 1's Task + context.
        2. Calls the Person 2 adapter's .run(task_ctx) method.
        3. Converts the Person 2 AgentResult back into Person 1's AgentRun.
    """

    def __init__(self, agent_id: str, p2_adapter: Any):
        """
        Args:
            agent_id:    identifier used on the leaderboard
            p2_adapter:  any Person 2 adapter that implements .run(TaskContext)
        """
        self._id      = agent_id
        self._adapter = p2_adapter

    @property
    def agent_id(self) -> str:
        return self._id

    def run_task(
        self,
        task:       Task,
        api_caller: Callable,   # Person 1's api_caller (unused — we use FakeAPIBridge)
        context:    Dict,
    ) -> AgentRun:
        """Convert Person 1's task format → Person 2 TaskContext, run, convert back."""

        # ── Build Person 2's TaskContext ──────────────────────────────────────
        try:
            from agents.base import TaskContext
        except ImportError:
            # Fallback if Person 2's backend is not on the Python path
            TaskContext = _SimpleTaskContext  # type: ignore

        # Inject live tool responses from Person 1's FakeAPIServer
        token      = context.get("valid_viewer_token", "")
        company_id = context.get("company_id", task.inputs.get("company_id", "acme"))
        environment = _hydrate_environment(task.environment, company_id, self._id, token)

        task_ctx = TaskContext(
            task_id              = task.id,
            title                = task.name,
            prompt               = task.prompt or task.description,
            environment          = environment,
            max_tokens           = task.max_tokens,
            timeout_seconds      = task.timeout_seconds,
            adversarial_elements = task.adversarial_elements,
        )

        # ── Run via Person 2's adapter ────────────────────────────────────────
        start  = time.time()
        result = self._adapter.run(task_ctx)
        elapsed = time.time() - start

        # ── Convert Person 2's AgentResult → Person 1's AgentRun ─────────────
        run = AgentRun(agent_id=self._id, task_id=task.id)

        for step in result.trace:
            run.add_step(AgentStep(
                step_num    = step.step,
                action      = step.tool if step.tool else step.action,
                inputs      = {"input": step.input} if step.input else {},
                output      = step.output,
                tokens_used = step.tokens or 0,
                timestamp   = step.timestamp,
            ))

        # Map success/failure
        if not result.success and result.error:
            run.complete(f"[ERROR] {result.error}")
        else:
            run.complete(result.final_answer or "")

        return run


def _hydrate_environment(
    environment: Dict,
    company_id:  str,
    agent_id:    str,
    token:       str,
) -> Dict:
    """
    Replace empty `response` dicts in tool definitions with live data
    pulled from Person 1's FakeAPIServer. This gives Person 2's adapters
    realistic, consistent data to work with.
    """
    api_bridge = FakeAPIBridge(agent_id=agent_id, token=token)
    hydrated_tools = []

    for tool in environment.get("tools", []):
        tool = dict(tool)   # shallow copy — don't mutate shared TOOL_DEFS
        if not tool.get("response"):
            resp = api_bridge.call(company_id, tool["name"], {})
            tool["response"] = resp.get("data") or {}
        hydrated_tools.append(tool)

    return {**environment, "tools": hydrated_tools,
            "data": {"company_id": company_id}}


class _SimpleTaskContext:
    """Fallback if Person 2's agents module isn't on the path."""
    def __init__(self, task_id, title, prompt, environment,
                 max_tokens, timeout_seconds, adversarial_elements):
        self.task_id              = task_id
        self.title                = title
        self.prompt               = prompt
        self.environment          = environment
        self.max_tokens           = max_tokens
        self.timeout_seconds      = timeout_seconds
        self.adversarial_elements = adversarial_elements


# ─── 3. task_to_db_dict() ────────────────────────────────────────────────────

def task_to_db_dict(task: Task) -> Dict:
    """
    Convert a Person 1 Task object to the dict format Person 2's
    DB seed script and SQLAlchemy model expects.

    Matches the column names in Person 2's models.Task:
        slug, title, description, category, difficulty,
        prompt, environment, expected_outcome, adversarial_elements,
        scoring_rubric, max_tokens, timeout_seconds, is_public
    """
    # Map Person 1 category names → Person 2 TaskCategory enum values
    category_map = {
        "data_retrieval": "tool_use",
        "write":          "multi_step",
        "multi_step":     "multi_step",
        "adversarial":    "adversarial",
    }

    return {
        "slug":                 task.id,          # T001, T042, …
        "title":                task.name,
        "description":          task.description,
        "category":             category_map.get(task.category, task.category),
        "difficulty":           task.difficulty,
        "prompt":               task.prompt or task.description,
        "environment":          task.environment,
        "expected_outcome":     task.expected_outcome,
        "adversarial_elements": task.adversarial_elements,
        "scoring_rubric":       task.scoring_rubric,
        "max_tokens":           task.max_tokens,
        "timeout_seconds":      task.timeout_seconds,
        "is_public":            task.is_public,
    }


# ─── 4. seed_p2_db() ─────────────────────────────────────────────────────────

def seed_p2_db(db_session: Any, overwrite: bool = False) -> int:
    """
    Seed Person 2's PostgreSQL database with all 104 Person 1 tasks.

    Args:
        db_session: a SQLAlchemy Session from Person 2's db.database.SessionLocal()
        overwrite:  if True, existing tasks are updated; if False, skipped

    Returns:
        number of tasks inserted/updated
    """
    try:
        import sys, os
        # Person 2's models must be importable
        import models as p2_models
    except ImportError:
        raise ImportError(
            "Cannot import Person 2's `models` module. "
            "Make sure Person 2's backend/ directory is on sys.path."
        )

    existing_slugs = {
        t.slug for t in db_session.query(p2_models.Task).all()
    }

    count = 0
    for p1_task in TASK_CATALOGUE:
        d = task_to_db_dict(p1_task)

        if d["slug"] in existing_slugs:
            if not overwrite:
                continue
            # Update existing
            db_task = db_session.query(p2_models.Task).filter(
                p2_models.Task.slug == d["slug"]
            ).first()
            for k, v in d.items():
                setattr(db_task, k, v)
        else:
            db_task = p2_models.Task(**d)
            db_session.add(db_task)

        count += 1

    db_session.commit()
    print(f"[Bridge] Seeded {count} tasks into Person 2's DB "
          f"({'with' if overwrite else 'without'} overwrite).")
    return count


# ─── 5. export_tasks_json() ──────────────────────────────────────────────────

def export_tasks_json(filepath: str = "p1_tasks_for_p2.json") -> str:
    """
    Export all tasks as JSON that Person 2's seed script can consume
    without needing Person 1's Python environment.
    """
    data = [task_to_db_dict(t) for t in TASK_CATALOGUE]
    payload = json.dumps(data, indent=2)
    with open(filepath, "w") as f:
        f.write(payload)
    print(f"[Bridge] Exported {len(data)} tasks to '{filepath}'.")
    return payload


# ─── CLI convenience ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AgentArena P1→P2 Bridge CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("export", help="Export tasks to JSON for Person 2")
    p_seed = sub.add_parser("seed", help="Seed Person 2's DB directly")
    p_seed.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()

    if args.cmd == "export":
        export_tasks_json("p1_tasks_for_p2.json")

    elif args.cmd == "seed":
        import sys
        # Person 2's backend must be on the path
        p2_path = os.environ.get("P2_BACKEND_PATH", "../backend")
        sys.path.insert(0, p2_path)
        from db.database import SessionLocal
        seed_p2_db(SessionLocal(), overwrite=args.overwrite)

    else:
        parser.print_help()
