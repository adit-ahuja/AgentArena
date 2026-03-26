"""
Custom Agent Adapter
For agents exposed as HTTP endpoints or Docker containers.
Companies submit their own agent and we call it via a standard REST interface.
"""

import time
import json
import httpx
from typing import Dict, Any, List
from agents.base import BaseAgent, AgentResult, TaskContext, TraceStep


# ── Standard AgentArena Agent Protocol ────────────────────────────────────────
#
# Request  POST /run
#   { "task_id", "prompt", "environment", "max_tokens", "timeout_seconds" }
#
# Response 200 OK
#   { "final_answer", "trace": [...], "tokens_used", "metadata" }
#
# ──────────────────────────────────────────────────────────────────────────────


class CustomHTTPAdapter(BaseAgent):
    """
    Calls a company's own agent at a given HTTP endpoint.

    Config keys:
        endpoint:   URL of the agent's /run endpoint
        api_key:    Bearer token (optional)
        timeout:    HTTP timeout seconds (default: 120)
    """

    def _validate_config(self):
        if "endpoint" not in self.config:
            raise ValueError("CustomHTTPAdapter requires 'endpoint'")

    def run(self, task: TaskContext) -> AgentResult:
        start  = time.time()
        trace: List[TraceStep] = []

        headers = {"Content-Type": "application/json"}
        if api_key := self.config.get("api_key"):
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "task_id":          task.task_id,
            "prompt":           task.prompt,
            "environment":      task.environment,
            "max_tokens":       task.max_tokens,
            "timeout_seconds":  task.timeout_seconds,
        }

        try:
            timeout = self.config.get("timeout", task.timeout_seconds + 10)
            trace.append(TraceStep(
                step=1, action="tool_call",
                tool="http_call", input={"url": self.config["endpoint"]},
                timestamp=time.time(),
            ))

            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    self.config["endpoint"],
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            elapsed = time.time() - start

            # Merge any trace steps the external agent returned
            for step in data.get("trace", []):
                trace.append(TraceStep(
                    step=step.get("step", 0),
                    action=step.get("action", "reasoning"),
                    tool=step.get("tool"),
                    input=step.get("input"),
                    output=step.get("output"),
                    timestamp=step.get("timestamp", time.time()),
                    tokens=step.get("tokens", 0),
                ))

            final_answer = data.get("final_answer", "")
            tokens_used  = data.get("tokens_used", 0)

            trace.append(TraceStep(
                step=len(trace) + 1,
                action="output",
                output=final_answer[:500],
                timestamp=time.time(),
            ))

            return AgentResult(
                final_answer=final_answer,
                trace=trace,
                tokens_used=tokens_used,
                time_seconds=elapsed,
                cost_usd=data.get("cost_usd", 0.0),
                success=True,
                metadata=data.get("metadata", {}),
            )

        except httpx.TimeoutException:
            elapsed = time.time() - start
            return AgentResult(
                final_answer="",
                trace=trace,
                tokens_used=0,
                time_seconds=elapsed,
                cost_usd=0.0,
                success=False,
                error=f"Agent endpoint timed out after {task.timeout_seconds}s",
            )
        except Exception as e:
            elapsed = time.time() - start
            return AgentResult(
                final_answer="",
                trace=trace,
                tokens_used=0,
                time_seconds=elapsed,
                cost_usd=0.0,
                success=False,
                error=str(e),
            )


class CustomDockerAdapter(BaseAgent):
    """
    Spins up an agent's Docker container, runs the task, tears it down.

    Config keys:
        docker_image:   e.g. "mycompany/my-agent:latest"
        env_vars:       dict of env vars to pass to the container
        memory_limit:   e.g. "512m"
        cpu_quota:      e.g. 50000 (50% of a core)
    """

    def _validate_config(self):
        if "docker_image" not in self.config:
            raise ValueError("CustomDockerAdapter requires 'docker_image'")

    def run(self, task: TaskContext) -> AgentResult:
        import docker
        start  = time.time()
        trace: List[TraceStep] = []

        client = docker.from_env()
        container = None

        try:
            task_json = json.dumps({
                "task_id":         task.task_id,
                "prompt":          task.prompt,
                "environment":     task.environment,
                "max_tokens":      task.max_tokens,
                "timeout_seconds": task.timeout_seconds,
            })

            env_vars = {
                "ARENA_TASK": task_json,
                **self.config.get("env_vars", {}),
            }

            trace.append(TraceStep(
                step=1, action="tool_call",
                tool="docker_run",
                input={"image": self.config["docker_image"]},
                timestamp=time.time(),
            ))

            container = client.containers.run(
                image=self.config["docker_image"],
                environment=env_vars,
                mem_limit=self.config.get("memory_limit", "1g"),
                cpu_quota=self.config.get("cpu_quota", 100000),
                network_mode="none",          # no internet access for sandboxing
                detach=True,
                remove=False,
            )

            container.wait(timeout=task.timeout_seconds + 5)
            logs = container.logs().decode("utf-8")

            # Agent should print JSON result to stdout
            result_data = json.loads(logs.strip().split("\n")[-1])
            elapsed     = time.time() - start

            final_answer = result_data.get("final_answer", "")
            tokens_used  = result_data.get("tokens_used", 0)

            for step in result_data.get("trace", []):
                trace.append(TraceStep(
                    step=step.get("step", 0),
                    action=step.get("action", "reasoning"),
                    tool=step.get("tool"),
                    input=step.get("input"),
                    output=step.get("output"),
                    timestamp=step.get("timestamp", time.time()),
                    tokens=step.get("tokens", 0),
                ))

            trace.append(TraceStep(
                step=len(trace) + 1,
                action="output",
                output=final_answer[:500],
                timestamp=time.time(),
            ))

            return AgentResult(
                final_answer=final_answer,
                trace=trace,
                tokens_used=tokens_used,
                time_seconds=elapsed,
                cost_usd=result_data.get("cost_usd", 0.0),
                success=True,
                metadata={"docker_image": self.config["docker_image"]},
            )

        except Exception as e:
            elapsed = time.time() - start
            return AgentResult(
                final_answer="",
                trace=trace,
                tokens_used=0,
                time_seconds=elapsed,
                cost_usd=0.0,
                success=False,
                error=str(e),
            )
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass


def build_adapter(agent_type: str, config: Dict[str, Any]) -> BaseAgent:
    """Factory — returns the right adapter for an agent type."""
    from agents.langchain_adapter import LangChainAdapter
    from agents.openai_adapter    import OpenAIAssistantsAdapter
    from agents.autogpt_adapter   import AutoGPTAdapter
    from agents.crewai_adapter    import CrewAIAdapter

    adapters = {
        "langchain":           LangChainAdapter,
        "openai_assistants":   OpenAIAssistantsAdapter,
        "autogpt":             AutoGPTAdapter,
        "crewai":              CrewAIAdapter,
        "custom_http":         CustomHTTPAdapter,
        "custom_docker":       CustomDockerAdapter,
    }
    cls = adapters.get(agent_type)
    if not cls:
        raise ValueError(f"Unknown agent_type: '{agent_type}'. Valid: {list(adapters)}")
    return cls(config)
