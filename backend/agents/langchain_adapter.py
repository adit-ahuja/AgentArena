"""
LangChain Agent Adapter
Wraps any LangChain agent (ReAct, OpenAI Tools, etc.) into the AgentArena interface.
"""

import time
import json
from typing import Dict, Any, List
from agents.base import BaseAgent, AgentResult, TaskContext, TraceStep


class LangChainAdapter(BaseAgent):
    """
    Adapter for LangChain-based agents.

    Config keys:
        llm_type:    "openai" | "anthropic" | "gemini"
        model:       e.g. "gpt-4o", "claude-3-sonnet"
        api_key:     LLM API key
        agent_type:  "react" | "openai_tools" | "structured_chat"
        tools:       list of tool names to give the agent
        temperature: float (default 0)
    """

    REQUIRED_CONFIG = ["llm_type", "model", "api_key"]

    def _validate_config(self):
        for key in self.REQUIRED_CONFIG:
            if key not in self.config:
                raise ValueError(f"LangChainAdapter requires config key: '{key}'")

    def _build_llm(self):
        from langchain_openai import ChatOpenAI
        from langchain_anthropic import ChatAnthropic

        llm_type = self.config["llm_type"]
        model    = self.config["model"]
        api_key  = self.config["api_key"]
        temp     = self.config.get("temperature", 0)

        if llm_type == "openai":
            return ChatOpenAI(model=model, api_key=api_key, temperature=temp)
        elif llm_type == "anthropic":
            return ChatAnthropic(model=model, api_key=api_key, temperature=temp)
        else:
            raise ValueError(f"Unsupported llm_type: {llm_type}")

    def _build_tools(self, environment: Dict[str, Any]) -> List:
        """Build fake environment tools from the task environment definition."""
        from langchain.tools import StructuredTool
        from pydantic import BaseModel, create_model

        tools = []
        for tool_def in environment.get("tools", []):
            name        = tool_def["name"]
            description = tool_def["description"]
            response    = tool_def.get("response", {})
            latency     = tool_def.get("latency_ms", 0) / 1000
            error_rate  = tool_def.get("error_rate", 0.0)

            InputModel = create_model(
                f"{name}Input",
                **{k: (str, ...) for k in tool_def.get("inputs", {}).keys()}
            )

            import random

            def make_func(resp, lat, err):
                def _func(**kwargs):
                    time.sleep(lat)
                    if random.random() < err:
                        raise RuntimeError("Simulated API error")
                    return json.dumps(resp)
                return _func

            tools.append(StructuredTool(
                name=name,
                description=description,
                func=make_func(response, latency, error_rate),
                args_schema=InputModel,
            ))

        return tools

    def run(self, task: TaskContext) -> AgentResult:
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain.prompts import PromptTemplate
        from langchain.callbacks.base import BaseCallbackHandler

        start = time.time()
        trace: List[TraceStep] = []
        step_counter = [0]
        total_tokens = [0]

        class ArenaCallbackHandler(BaseCallbackHandler):
            def on_llm_start(self, serialized, prompts, **kwargs):
                step_counter[0] += 1
                trace.append(TraceStep(
                    step=step_counter[0],
                    action="reasoning",
                    input=prompts[0][:500] if prompts else None,
                    timestamp=time.time(),
                ))

            def on_llm_end(self, response, **kwargs):
                tokens = getattr(response, "llm_output", {})
                usage  = tokens.get("token_usage", {}) if tokens else {}
                t      = usage.get("total_tokens", 0)
                total_tokens[0] += t
                if trace:
                    trace[-1].output = response.generations[0][0].text[:500]
                    trace[-1].tokens = t

            def on_tool_start(self, serialized, input_str, **kwargs):
                step_counter[0] += 1
                trace.append(TraceStep(
                    step=step_counter[0],
                    action="tool_call",
                    tool=serialized.get("name"),
                    input=input_str,
                    timestamp=time.time(),
                ))

            def on_tool_end(self, output, **kwargs):
                if trace:
                    trace[-1].action = "tool_result"
                    trace[-1].output = str(output)[:500]

            def on_tool_error(self, error, **kwargs):
                if trace:
                    trace[-1].error = str(error)

        try:
            llm    = self._build_llm()
            tools  = self._build_tools(task.environment)
            cb     = ArenaCallbackHandler()

            react_prompt = PromptTemplate.from_template(
                "You are a helpful AI agent. Answer the following task.\n\n"
                "Task: {input}\n\n"
                "You have access to these tools: {tools}\n"
                "Tool names: {tool_names}\n\n"
                "Use this format:\n"
                "Thought: ...\nAction: ...\nAction Input: ...\nObservation: ...\n"
                "... (repeat as needed)\n"
                "Thought: I now know the final answer\nFinal Answer: ...\n\n"
                "Scratchpad: {agent_scratchpad}"
            )

            agent    = create_react_agent(llm=llm, tools=tools, prompt=react_prompt)
            executor = AgentExecutor(
                agent=agent,
                tools=tools,
                callbacks=[cb],
                max_iterations=10,
                verbose=False,
                handle_parsing_errors=True,
            )

            result = executor.invoke(
                {"input": task.prompt},
                config={"callbacks": [cb]},
            )
            final_answer = result.get("output", "")
            elapsed      = time.time() - start

            # Add final output step
            trace.append(TraceStep(
                step=step_counter[0] + 1,
                action="output",
                output=final_answer,
                timestamp=time.time(),
            ))

            return AgentResult(
                final_answer=final_answer,
                trace=trace,
                tokens_used=total_tokens[0],
                time_seconds=elapsed,
                cost_usd=self.estimate_cost(total_tokens[0], self.config["model"]),
                success=True,
                metadata={"agent_type": "langchain_react"},
            )

        except Exception as e:
            elapsed = time.time() - start
            return AgentResult(
                final_answer="",
                trace=trace,
                tokens_used=total_tokens[0],
                time_seconds=elapsed,
                cost_usd=0.0,
                success=False,
                error=str(e),
            )
