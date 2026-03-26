"""
Base Agent Interface
All agent adapters must inherit from BaseAgent and implement the `run` method.
The adapter translates between AgentArena's task format and the agent's native API.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
import time


@dataclass
class TraceStep:
    """A single step in the agent's execution trace."""
    step:      int
    action:    str              # "reasoning" | "tool_call" | "tool_result" | "output"
    tool:      Optional[str] = None
    input:     Optional[Any] = None
    output:    Optional[Any] = None
    timestamp: float = field(default_factory=time.time)
    tokens:    int = 0
    error:     Optional[str] = None


@dataclass
class AgentResult:
    """Standardized result returned by every agent adapter."""
    final_answer:    str
    trace:           List[TraceStep]
    tokens_used:     int
    time_seconds:    float
    cost_usd:        float
    success:         bool
    error:           Optional[str] = None
    metadata:        Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskContext:
    """The task payload handed to each agent."""
    task_id:              str
    title:                str
    prompt:               str
    environment:          Dict[str, Any]   # fake APIs, fake data
    max_tokens:           int
    timeout_seconds:      int
    adversarial_elements: List[str]


class BaseAgent(ABC):
    """
    Abstract base class for all AgentArena agent adapters.

    Subclasses must implement:
        - run(task: TaskContext) -> AgentResult
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._validate_config()

    def _validate_config(self):
        """Override to validate required config fields."""
        pass

    @abstractmethod
    def run(self, task: TaskContext) -> AgentResult:
        """
        Execute the agent on a given task.

        Args:
            task: TaskContext with all task details and environment

        Returns:
            AgentResult with trace, scores, and final answer
        """
        raise NotImplementedError

    def _make_trace_step(
        self,
        step: int,
        action: str,
        tool: Optional[str] = None,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        tokens: int = 0,
        error: Optional[str] = None,
    ) -> TraceStep:
        return TraceStep(
            step=step,
            action=action,
            tool=tool,
            input=input_data,
            output=output_data,
            timestamp=time.time(),
            tokens=tokens,
            error=error,
        )

    @staticmethod
    def estimate_cost(tokens: int, model: str) -> float:
        """Rough cost estimation by model. Update as pricing changes."""
        cost_per_1k = {
            "gpt-4o":            0.005,
            "gpt-4-turbo":       0.010,
            "gpt-3.5-turbo":     0.0005,
            "claude-3-opus":     0.015,
            "claude-3-sonnet":   0.003,
            "claude-3-haiku":    0.00025,
            "gemini-1.5-pro":    0.007,
            "gemini-1.5-flash":  0.00035,
        }
        rate = cost_per_1k.get(model, 0.005)
        return round((tokens / 1000) * rate, 6)
