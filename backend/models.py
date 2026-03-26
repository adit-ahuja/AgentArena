from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime,
    ForeignKey, JSON, Text, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base
import enum
import uuid


def gen_uuid():
    return str(uuid.uuid4())


# ─── Enums ────────────────────────────────────────────────────────────────────

class AgentStatus(str, enum.Enum):
    pending   = "pending"
    active    = "active"
    suspended = "suspended"

class RunStatus(str, enum.Enum):
    queued    = "queued"
    running   = "running"
    completed = "completed"
    failed    = "failed"
    timeout   = "timeout"

class AgentType(str, enum.Enum):
    langchain  = "langchain"
    autogpt    = "autogpt"
    openai     = "openai_assistants"
    crewai     = "crewai"
    custom     = "custom"

class TaskCategory(str, enum.Enum):
    tool_use         = "tool_use"
    multi_step       = "multi_step"
    adversarial      = "adversarial"
    rag              = "rag"
    planning         = "planning"
    safety           = "safety"
    hallucination    = "hallucination"
    cost_efficiency  = "cost_efficiency"


# ─── Models ───────────────────────────────────────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id              = Column(String, primary_key=True, default=gen_uuid)
    name            = Column(String, nullable=False, index=True)
    description     = Column(Text, nullable=True)
    agent_type      = Column(SAEnum(AgentType), nullable=False)
    status          = Column(SAEnum(AgentStatus), default=AgentStatus.pending)
    submitter_email = Column(String, nullable=True)
    docker_image    = Column(String, nullable=True)   # for containerized agents
    api_endpoint    = Column(String, nullable=True)   # for API-based agents
    config          = Column(JSON, default=dict)       # adapter config
    model_backbone  = Column(String, nullable=True)    # e.g. "gpt-4o", "claude-3"
    version         = Column(String, default="1.0.0")
    is_verified     = Column(Boolean, default=False)
    elo_rating      = Column(Float, default=1200.0)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    runs            = relationship("Run", back_populates="agent")
    scores          = relationship("AgentScore", back_populates="agent")


class Task(Base):
    __tablename__ = "tasks"

    id                  = Column(String, primary_key=True, default=gen_uuid)
    slug                = Column(String, unique=True, nullable=False)  # "task_001"
    title               = Column(String, nullable=False)
    description         = Column(Text, nullable=False)
    category            = Column(SAEnum(TaskCategory), nullable=False)
    difficulty          = Column(String, default="medium")  # easy/medium/hard/expert
    prompt              = Column(Text, nullable=False)
    environment         = Column(JSON, default=dict)         # fake APIs, data
    expected_outcome    = Column(JSON, default=dict)
    adversarial_elements = Column(JSON, default=list)
    scoring_rubric      = Column(JSON, default=dict)
    max_tokens          = Column(Integer, default=4000)
    timeout_seconds     = Column(Integer, default=120)
    is_public           = Column(Boolean, default=True)      # hidden tasks for anti-gaming
    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    task_results        = relationship("TaskResult", back_populates="task")


class Run(Base):
    __tablename__ = "runs"

    id              = Column(String, primary_key=True, default=gen_uuid)
    agent_id        = Column(String, ForeignKey("agents.id"), nullable=False)
    status          = Column(SAEnum(RunStatus), default=RunStatus.queued)
    task_suite      = Column(String, default="full")      # "full" | "quick" | custom
    total_tasks     = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    started_at      = Column(DateTime(timezone=True), nullable=True)
    finished_at     = Column(DateTime(timezone=True), nullable=True)
    total_tokens    = Column(Integer, default=0)
    total_cost_usd  = Column(Float, default=0.0)
    wall_time_secs  = Column(Float, default=0.0)
    error           = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    agent           = relationship("Agent", back_populates="runs")
    task_results    = relationship("TaskResult", back_populates="run")
    scores          = relationship("AgentScore", back_populates="run", uselist=False)


class TaskResult(Base):
    __tablename__ = "task_results"

    id                    = Column(String, primary_key=True, default=gen_uuid)
    run_id                = Column(String, ForeignKey("runs.id"), nullable=False)
    task_id               = Column(String, ForeignKey("tasks.id"), nullable=False)
    status                = Column(String, default="pending")  # pass/fail/partial/timeout
    agent_output          = Column(Text, nullable=True)
    trace                 = Column(JSON, default=list)          # step-by-step actions
    tokens_used           = Column(Integer, default=0)
    time_seconds          = Column(Float, default=0.0)
    goal_completion_score = Column(Float, nullable=True)        # 0-100
    hallucination_score   = Column(Float, nullable=True)        # 0-100 (lower=worse)
    safety_score          = Column(Float, nullable=True)        # 0-100
    adversarial_score     = Column(Float, nullable=True)        # 0-100
    cost_score            = Column(Float, nullable=True)        # 0-100
    failure_reasons       = Column(JSON, default=list)
    ai_analysis           = Column(Text, nullable=True)         # AI-generated failure analysis
    created_at            = Column(DateTime(timezone=True), server_default=func.now())

    run                   = relationship("Run", back_populates="task_results")
    task                  = relationship("Task", back_populates="task_results")


class AgentScore(Base):
    __tablename__ = "agent_scores"

    id                       = Column(String, primary_key=True, default=gen_uuid)
    agent_id                 = Column(String, ForeignKey("agents.id"), nullable=False)
    run_id                   = Column(String, ForeignKey("runs.id"), nullable=False)
    aas_score                = Column(Float, nullable=False)   # AgentArena Score (0-100)
    goal_completion_avg      = Column(Float, default=0.0)
    hallucination_avg        = Column(Float, default=0.0)
    safety_avg               = Column(Float, default=0.0)
    adversarial_avg          = Column(Float, default=0.0)
    cost_avg                 = Column(Float, default=0.0)
    pass_rate                = Column(Float, default=0.0)
    elo_before               = Column(Float, nullable=True)
    elo_after                = Column(Float, nullable=True)
    confidence_interval_low  = Column(Float, nullable=True)
    confidence_interval_high = Column(Float, nullable=True)
    created_at               = Column(DateTime(timezone=True), server_default=func.now())

    agent                    = relationship("Agent", back_populates="scores")
    run                      = relationship("Run", back_populates="scores")


class EloHistory(Base):
    __tablename__ = "elo_history"

    id         = Column(String, primary_key=True, default=gen_uuid)
    agent_id   = Column(String, ForeignKey("agents.id"), nullable=False)
    run_id     = Column(String, ForeignKey("runs.id"), nullable=False)
    elo_before = Column(Float, nullable=False)
    elo_after  = Column(Float, nullable=False)
    delta      = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
