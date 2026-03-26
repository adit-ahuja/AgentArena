from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any, Dict
from enum import Enum
from datetime import datetime


# ─── Enums (mirroring models) ─────────────────────────────────────────────────

class AgentType(str, Enum):
    langchain  = "langchain"
    autogpt    = "autogpt"
    openai     = "openai_assistants"
    crewai     = "crewai"
    custom     = "custom"

class TaskCategory(str, Enum):
    tool_use        = "tool_use"
    multi_step      = "multi_step"
    adversarial     = "adversarial"
    rag             = "rag"
    planning        = "planning"
    safety          = "safety"
    hallucination   = "hallucination"
    cost_efficiency = "cost_efficiency"


# ─── Agent ────────────────────────────────────────────────────────────────────

class AgentSubmit(BaseModel):
    name:            str
    description:     Optional[str] = None
    agent_type:      AgentType
    model_backbone:  Optional[str] = None
    docker_image:    Optional[str] = None
    api_endpoint:    Optional[str] = None
    config:          Dict[str, Any] = {}
    version:         str = "1.0.0"
    submitter_email: Optional[str] = None


class AgentOut(BaseModel):
    id:             str
    name:           str
    description:    Optional[str]
    agent_type:     str
    model_backbone: Optional[str]
    version:        str
    elo_rating:     float
    is_verified:    bool
    status:         str
    created_at:     datetime

    class Config:
        from_attributes = True


# ─── Task ─────────────────────────────────────────────────────────────────────

class TaskOut(BaseModel):
    id:          str
    slug:        str
    title:       str
    description: str
    category:    str
    difficulty:  str
    is_public:   bool

    class Config:
        from_attributes = True


# ─── Run ──────────────────────────────────────────────────────────────────────

class RunCreate(BaseModel):
    agent_id:   str
    task_suite: str = "full"   # "full" | "quick" | list of task slugs
    task_ids:   Optional[List[str]] = None


class RunOut(BaseModel):
    id:              str
    agent_id:        str
    status:          str
    total_tasks:     int
    completed_tasks: int
    total_tokens:    int
    total_cost_usd:  float
    wall_time_secs:  float
    error:           Optional[str]
    started_at:      Optional[datetime]
    finished_at:     Optional[datetime]
    created_at:      datetime

    class Config:
        from_attributes = True


# ─── TraceStep ────────────────────────────────────────────────────────────────

class TraceStep(BaseModel):
    step:      int
    action:    str             # "tool_call" | "reasoning" | "output"
    tool:      Optional[str]
    input:     Optional[Any]
    output:    Optional[Any]
    timestamp: float           # seconds from run start
    tokens:    Optional[int]


# ─── TaskResult ───────────────────────────────────────────────────────────────

class TaskResultOut(BaseModel):
    id:                    str
    run_id:                str
    task_id:               str
    status:                str
    agent_output:          Optional[str]
    trace:                 List[Dict]
    tokens_used:           int
    time_seconds:          float
    goal_completion_score: Optional[float]
    hallucination_score:   Optional[float]
    safety_score:          Optional[float]
    adversarial_score:     Optional[float]
    cost_score:            Optional[float]
    failure_reasons:       List[str]
    ai_analysis:           Optional[str]

    class Config:
        from_attributes = True


# ─── AgentScore ───────────────────────────────────────────────────────────────

class AgentScoreOut(BaseModel):
    id:                      str
    agent_id:                str
    run_id:                  str
    aas_score:               float
    goal_completion_avg:     float
    hallucination_avg:       float
    safety_avg:              float
    adversarial_avg:         float
    cost_avg:                float
    pass_rate:               float
    elo_before:              Optional[float]
    elo_after:               Optional[float]
    confidence_interval_low: Optional[float]
    confidence_interval_high:Optional[float]
    created_at:              datetime

    class Config:
        from_attributes = True


# ─── Leaderboard ──────────────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank:             int
    agent_id:         str
    agent_name:       str
    agent_type:       str
    model_backbone:   Optional[str]
    aas_score:        float
    goal_completion:  float
    hallucination:    float
    safety:           float
    adversarial:      float
    cost:             float
    pass_rate:        float
    elo_rating:       float
    is_verified:      bool
    runs_count:       int
    confidence_low:   Optional[float]
    confidence_high:  Optional[float]


# ─── Webhook (CI/CD integration) ──────────────────────────────────────────────

class WebhookConfig(BaseModel):
    agent_id:   str
    webhook_url: str
    secret:     str
    auto_run_on_push: bool = True
    task_suite: str = "quick"


# ─── Scoring weights (for dynamic re-ranking) ─────────────────────────────────

class ScoringWeights(BaseModel):
    goal_completion: float = Field(0.30, ge=0, le=1)
    hallucination:   float = Field(0.20, ge=0, le=1)
    safety:          float = Field(0.20, ge=0, le=1)
    adversarial:     float = Field(0.20, ge=0, le=1)
    cost:            float = Field(0.10, ge=0, le=1)
