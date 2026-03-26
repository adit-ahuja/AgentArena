"""
OpenAI Assistants API Adapter
Wraps an OpenAI Assistant into the AgentArena interface.
"""

import time
import json
from typing import Dict, Any, List, Optional
from agents.base import BaseAgent, AgentResult, TaskContext, TraceStep


class OpenAIAssistantsAdapter(BaseAgent):
    """
    Adapter for OpenAI Assistants API.

    Config keys:
        api_key:       OpenAI API key
        model:         e.g. "gpt-4o"
        assistant_id:  (optional) existing assistant ID; creates new one if absent
        tools:         list of tool dicts (type: "function", ...)
        instructions:  system instructions for the assistant
    """

    def _validate_config(self):
        if "api_key" not in self.config:
            raise ValueError("OpenAIAssistantsAdapter requires 'api_key'")

    def _get_client(self):
        from openai import OpenAI
        return OpenAI(api_key=self.config["api_key"])

    def _build_function_tools(self, environment: Dict[str, Any]) -> List[Dict]:
        """Convert environment tool definitions to OpenAI function schemas."""
        tools = []
        for tool_def in environment.get("tools", []):
            params = {
                "type": "object",
                "properties": {
                    k: {"type": "string", "description": v}
                    for k, v in tool_def.get("inputs", {}).items()
                },
                "required": list(tool_def.get("inputs", {}).keys()),
            }
            tools.append({
                "type": "function",
                "function": {
                    "name":        tool_def["name"],
                    "description": tool_def["description"],
                    "parameters":  params,
                },
            })
        return tools

    def _execute_tool_call(
        self,
        tool_name: str,
        tool_args: Dict,
        environment: Dict[str, Any],
    ) -> str:
        """Look up the fake tool in the environment and return its response."""
        import random
        for tool_def in environment.get("tools", []):
            if tool_def["name"] == tool_name:
                latency = tool_def.get("latency_ms", 0) / 1000
                time.sleep(latency)
                if random.random() < tool_def.get("error_rate", 0.0):
                    return json.dumps({"error": "Simulated API error"})
                return json.dumps(tool_def.get("response", {}))
        return json.dumps({"error": f"Tool '{tool_name}' not found in environment"})

    def run(self, task: TaskContext) -> AgentResult:
        client = self._get_client()
        start  = time.time()
        trace: List[TraceStep] = []
        total_tokens = 0
        step = 0

        try:
            # ── Create or reuse assistant ──────────────────────────────────────
            assistant_id = self.config.get("assistant_id")
            fn_tools     = self._build_function_tools(task.environment)

            if not assistant_id:
                assistant = client.beta.assistants.create(
                    model=self.config.get("model", "gpt-4o"),
                    name="AgentArena Test Agent",
                    instructions=self.config.get(
                        "instructions",
                        "You are a capable AI agent. Complete the given task accurately.",
                    ),
                    tools=fn_tools,
                )
                assistant_id = assistant.id

            # ── Create thread & message ────────────────────────────────────────
            thread  = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=task.prompt,
            )

            step += 1
            trace.append(TraceStep(step=step, action="reasoning",
                                   input=task.prompt[:300], timestamp=time.time()))

            # ── Poll run ───────────────────────────────────────────────────────
            run_obj = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant_id,
            )

            deadline = time.time() + task.timeout_seconds

            while True:
                if time.time() > deadline:
                    client.beta.threads.runs.cancel(
                        thread_id=thread.id, run_id=run_obj.id
                    )
                    raise TimeoutError("Agent exceeded time limit")

                run_obj = client.beta.threads.runs.retrieve(
                    thread_id=thread.id, run_id=run_obj.id
                )

                if run_obj.status == "completed":
                    break

                elif run_obj.status == "requires_action":
                    tool_outputs = []
                    for tc in run_obj.required_action.submit_tool_outputs.tool_calls:
                        args = json.loads(tc.function.arguments or "{}")
                        step += 1
                        trace.append(TraceStep(
                            step=step, action="tool_call",
                            tool=tc.function.name, input=args, timestamp=time.time()
                        ))

                        output = self._execute_tool_call(
                            tc.function.name, args, task.environment
                        )

                        step += 1
                        trace.append(TraceStep(
                            step=step, action="tool_result",
                            tool=tc.function.name, output=output, timestamp=time.time()
                        ))
                        tool_outputs.append({"tool_call_id": tc.id, "output": output})

                    client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread.id,
                        run_id=run_obj.id,
                        tool_outputs=tool_outputs,
                    )

                elif run_obj.status in ("failed", "cancelled", "expired"):
                    raise RuntimeError(f"Assistant run {run_obj.status}")

                else:
                    time.sleep(0.5)

            # ── Extract answer ─────────────────────────────────────────────────
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            final_answer = ""
            for msg in messages.data:
                if msg.role == "assistant":
                    for blk in msg.content:
                        if blk.type == "text":
                            final_answer = blk.text.value
                            break
                    if final_answer:
                        break

            # token usage
            if run_obj.usage:
                total_tokens = run_obj.usage.total_tokens

            elapsed = time.time() - start
            step += 1
            trace.append(TraceStep(step=step, action="output",
                                   output=final_answer[:500], timestamp=time.time()))

            return AgentResult(
                final_answer=final_answer,
                trace=trace,
                tokens_used=total_tokens,
                time_seconds=elapsed,
                cost_usd=self.estimate_cost(total_tokens, self.config.get("model", "gpt-4o")),
                success=True,
                metadata={"assistant_id": assistant_id, "thread_id": thread.id},
            )

        except Exception as e:
            elapsed = time.time() - start
            return AgentResult(
                final_answer="",
                trace=trace,
                tokens_used=total_tokens,
                time_seconds=elapsed,
                cost_usd=0.0,
                success=False,
                error=str(e),
            )
