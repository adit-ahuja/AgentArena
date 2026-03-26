"""
AutoGPT Agent Adapter
Wraps AutoGPT (v0.5+) in the AgentArena interface using its REST API mode.

AutoGPT exposes a REST server when run with --enable-api.
We POST tasks to it and poll for completion.

Config keys:
    endpoint:     AutoGPT server URL (default: http://localhost:8080)
    api_key:      AutoGPT API key (if auth enabled)
    agent_name:   Name for the AutoGPT agent instance
    timeout:      Max seconds to wait for task completion
"""

import time
import json
import httpx
from typing import Dict, Any, List, Optional

from agents.base import BaseAgent, AgentResult, TaskContext, TraceStep


class AutoGPTAdapter(BaseAgent):
    """
    Adapter for AutoGPT v0.5+ running in API mode.

    Start AutoGPT with:
        python autogpt --enable-api --api-port 8080

    AgentArena then sends tasks to its REST interface.
    """

    REQUIRED_CONFIG = ["endpoint"]

    def _validate_config(self):
        for k in self.REQUIRED_CONFIG:
            if k not in self.config:
                raise ValueError(f"AutoGPTAdapter requires config key: '{k}'")

    def _headers(self) -> Dict:
        h = {"Content-Type": "application/json"}
        if key := self.config.get("api_key"):
            h["Authorization"] = f"Bearer {key}"
        return h

    def run(self, task: TaskContext) -> AgentResult:
        base_url = self.config["endpoint"].rstrip("/")
        timeout  = self.config.get("timeout", task.timeout_seconds + 10)
        trace: List[TraceStep] = []
        start = time.time()

        # Build a rich prompt that includes environment tool descriptions
        tool_descriptions = "\n".join(
            f"- {t['name']}: {t['description']}"
            for t in task.environment.get("tools", [])
        )
        full_prompt = (
            f"{task.prompt}\n\n"
            f"Available tools:\n{tool_descriptions}\n\n"
            "Complete this task step by step and provide a clear final answer."
        )

        try:
            with httpx.Client(timeout=timeout, headers=self._headers()) as client:

                # Step 1: Create agent task
                trace.append(TraceStep(
                    step=1, action="reasoning",
                    input=f"Creating AutoGPT task: {task.title}",
                    timestamp=time.time(),
                ))

                create_resp = client.post(f"{base_url}/ap/v1/agent/tasks", json={
                    "input":              full_prompt,
                    "additional_input":   {
                        "task_id":    task.task_id,
                        "max_steps":  10,
                    },
                })
                create_resp.raise_for_status()
                task_data = create_resp.json()
                agent_task_id = task_data.get("task_id") or task_data.get("id")

                trace[0].output = f"AutoGPT task created: {agent_task_id}"

                # Step 2: Execute steps (AutoGPT Agent Protocol)
                step_num = 1
                final_output = ""
                deadline = time.time() + task.timeout_seconds

                while time.time() < deadline:
                    # Trigger next step
                    step_resp = client.post(
                        f"{base_url}/ap/v1/agent/tasks/{agent_task_id}/steps",
                        json={"input": None},
                    )
                    step_resp.raise_for_status()
                    step_data = step_resp.json()

                    step_num += 1
                    output_text = step_data.get("output", "")
                    is_last = step_data.get("is_last", False)

                    trace.append(TraceStep(
                        step=step_num,
                        action="tool_call" if step_data.get("name") else "reasoning",
                        tool=step_data.get("name"),
                        input=step_data.get("input"),
                        output=str(output_text)[:500],
                        timestamp=time.time(),
                        tokens=step_data.get("additional_output", {}).get("tokens_used", 0),
                    ))

                    if output_text:
                        final_output = str(output_text)

                    if is_last or step_num > 15:
                        break

                    time.sleep(0.5)

                elapsed = time.time() - start
                total_tokens = sum(s.tokens for s in trace)

                trace.append(TraceStep(
                    step=step_num + 1, action="output",
                    output=final_output[:500], timestamp=time.time(),
                ))

                return AgentResult(
                    final_answer=final_output,
                    trace=trace,
                    tokens_used=total_tokens,
                    time_seconds=elapsed,
                    cost_usd=self.estimate_cost(total_tokens,
                                                self.config.get("model", "gpt-4o")),
                    success=bool(final_output),
                    metadata={"autogpt_task_id": agent_task_id,
                              "agent_name": self.config.get("agent_name", "AutoGPT")},
                )

        except httpx.ConnectError:
            elapsed = time.time() - start
            return AgentResult(
                final_answer="",
                trace=trace,
                tokens_used=0,
                time_seconds=elapsed,
                cost_usd=0.0,
                success=False,
                error=(
                    f"Cannot connect to AutoGPT at {base_url}. "
                    "Start with: python autogpt --enable-api --api-port 8080"
                ),
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
