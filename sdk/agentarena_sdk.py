"""
AgentArena Python SDK
Wrap your agent in 3 lines and submit to the benchmark.

Usage:
    from agentarena_sdk import ArenaAgent, arena_run

    @ArenaAgent(name="My GPT-4o Agent", model="gpt-4o")
    def my_agent(task):
        # your existing agent code here
        answer = call_your_llm(task["prompt"])
        return {"final_answer": answer}

    # Run locally against the full task suite
    if __name__ == "__main__":
        arena_run(my_agent, suite="quick")
"""

import os
import time
import json
import inspect
import functools
import threading
from typing import Callable, Optional, Dict, Any, List
import httpx

__version__ = "1.0.0"

DEFAULT_API = os.environ.get("ARENA_API_URL", "http://localhost:8000")


# ── Decorator ─────────────────────────────────────────────────────────────────

class ArenaAgent:
    """
    Decorator that registers a Python function as an AgentArena agent.

    Example:
        @ArenaAgent(name="My Agent", model="gpt-4o", agent_type="custom")
        def run_agent(task: dict) -> dict:
            answer = my_llm(task["prompt"])
            return {"final_answer": answer, "tokens_used": 500}
    """

    def __init__(
        self,
        name:        str,
        model:       str = "",
        agent_type:  str = "custom",
        description: str = "",
        version:     str = "1.0.0",
        api_url:     str = DEFAULT_API,
    ):
        self.name        = name
        self.model       = model
        self.agent_type  = agent_type
        self.description = description
        self.version     = version
        self.api_url     = api_url
        self._agent_id: Optional[str] = None
        self._fn: Optional[Callable] = None

    def __call__(self, fn: Callable) -> "ArenaAgent":
        self._fn = fn
        functools.update_wrapper(self, fn)
        return self

    def run_task(self, task: dict) -> dict:
        """Run the wrapped agent function on a task dict."""
        if not self._fn:
            raise RuntimeError("No agent function registered.")
        start  = time.time()
        result = self._fn(task)
        elapsed = time.time() - start

        # Normalize result
        if isinstance(result, str):
            result = {"final_answer": result}
        result.setdefault("time_seconds", round(elapsed, 2))
        return result

    def submit(self, email: Optional[str] = None) -> str:
        """Register this agent with the AgentArena API and return its agent_id."""
        client = httpx.Client(timeout=30, base_url=self.api_url)

        # Start a local HTTP server for the agent
        server = _AgentServer(self)
        server.start()
        endpoint = server.url

        payload = {
            "name":            self.name,
            "agent_type":      self.agent_type,
            "model_backbone":  self.model,
            "description":     self.description,
            "version":         self.version,
            "api_endpoint":    endpoint,
            "submitter_email": email or "",
            "config":          {"endpoint": endpoint},
        }
        resp = client.post("/api/agents/", json=payload)
        resp.raise_for_status()
        self._agent_id = resp.json()["id"]
        return self._agent_id

    def benchmark(
        self,
        suite:  str = "quick",
        watch:  bool = True,
        email:  Optional[str] = None,
    ) -> dict:
        """Submit + run a benchmark. Returns the final score dict."""
        print(f"[AgentArena] Submitting '{self.name}'…")
        agent_id = self.submit(email=email)
        print(f"[AgentArena] Agent ID: {agent_id}")

        client   = httpx.Client(timeout=30, base_url=self.api_url)
        run_resp = client.post("/api/runs/", json={
            "agent_id": agent_id, "task_suite": suite
        })
        run_resp.raise_for_status()
        run = run_resp.json()
        run_id = run["id"]
        print(f"[AgentArena] Run started: {run_id} (suite={suite})")

        if watch:
            return self._watch(run_id, client)
        return run

    def _watch(self, run_id: str, client: httpx.Client) -> dict:
        print("[AgentArena] Waiting for results", end="", flush=True)
        while True:
            time.sleep(3)
            run = client.get(f"/api/runs/{run_id}").json()
            print(".", end="", flush=True)
            if run["status"] in ("completed", "failed", "timeout"):
                print()
                try:
                    score = client.get(f"/api/runs/{run_id}/score").json()
                    print(f"\n[AgentArena] ✓ Done! AAS Score: {score['aas_score']:.1f}/100")
                    _print_score(score)
                    return score
                except Exception:
                    return run
        return {}


def _print_score(score: dict):
    dims = [
        ("Goal Completion",    "goal_completion_avg"),
        ("Anti-Hallucination", "hallucination_avg"),
        ("Safety",             "safety_avg"),
        ("Adversarial",        "adversarial_avg"),
        ("Cost Efficiency",    "cost_avg"),
    ]
    for label, key in dims:
        val  = score.get(key, 0)
        bar  = "█" * int(val / 5) + "░" * (20 - int(val / 5))
        print(f"  {label:22s} {bar} {val:.1f}")
    print(f"\n  Pass rate: {score.get('pass_rate', 0):.1f}%")


# ── Convenience function ──────────────────────────────────────────────────────

def arena_run(
    agent_fn:  Callable,
    name:      str = "",
    model:     str = "",
    suite:     str = "quick",
    api_url:   str = DEFAULT_API,
) -> dict:
    """
    One-liner to benchmark any callable.

        result = arena_run(my_agent_fn, name="My Agent", model="gpt-4o")
    """
    agent = ArenaAgent(
        name=name or agent_fn.__name__,
        model=model,
        api_url=api_url,
    )
    agent._fn = agent_fn
    return agent.benchmark(suite=suite)


# ── Minimal local HTTP server ─────────────────────────────────────────────────

class _AgentServer:
    """
    Spins up a tiny HTTP server on localhost so AgentArena can call
    the wrapped Python function over the standard REST protocol.
    """

    def __init__(self, agent: ArenaAgent, port: int = 0):
        self.agent = agent
        self.port  = port
        self.url   = ""
        self._thread: Optional[threading.Thread] = None

    def start(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import socket

        agent = self.agent

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # silence access logs

            def do_POST(self):
                if self.path != "/run":
                    self.send_response(404)
                    self.end_headers()
                    return

                length  = int(self.headers.get("Content-Length", 0))
                body    = self.rfile.read(length)
                task    = json.loads(body)

                try:
                    result = agent.run_task(task)
                    payload = json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except Exception as e:
                    err = json.dumps({"error": str(e)}).encode()
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(err)

        # bind to random free port
        server = HTTPServer(("0.0.0.0", 0), Handler)
        self.port = server.server_address[1]
        self.url  = f"http://host.docker.internal:{self.port}/run"

        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()


# ── Task helper ───────────────────────────────────────────────────────────────

class ArenaTask:
    """
    Helper to make task dicts easy to work with inside your agent function.

    Example:
        @ArenaAgent(name="My Agent")
        def run(raw_task: dict) -> dict:
            task = ArenaTask(raw_task)
            result = my_llm(task.prompt, tools=task.tools)
            return task.respond(final_answer=result)
    """

    def __init__(self, raw: dict):
        self.task_id              = raw.get("task_id", "")
        self.prompt               = raw.get("prompt", "")
        self.environment          = raw.get("environment", {})
        self.max_tokens           = raw.get("max_tokens", 4000)
        self.timeout_seconds      = raw.get("timeout_seconds", 120)
        self.adversarial_elements = raw.get("adversarial_elements", [])

    @property
    def tools(self) -> List[dict]:
        return self.environment.get("tools", [])

    @property
    def fake_data(self) -> dict:
        return self.environment.get("data", {})

    def respond(
        self,
        final_answer: str,
        trace: Optional[List[dict]] = None,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        metadata: Optional[dict] = None,
    ) -> dict:
        return {
            "final_answer": final_answer,
            "trace":        trace or [],
            "tokens_used":  tokens_used,
            "cost_usd":     cost_usd,
            "metadata":     metadata or {},
        }
