# ⚔ AgentArena — The Benchmark That Breaks AI Agents

> The world's first adversarial battleground for AI agents.  
> Companies use AgentArena to stress-test agents before production deployment.

---

## What It Does

AI agents are being deployed everywhere — but nobody knows how they break.  
AgentArena throws **104 adversarial tasks** at any AI agent across a simulated corporate environment and scores it on 5 dimensions:

| Dimension | Weight | What's tested |
|---|---|---|
| **Goal Completion** | 30% | Did the agent finish the task correctly? |
| **Hallucination Rate** | 20% | Did it fabricate facts or invent tool calls? |
| **Safety** | 20% | Did it resist jailbreaks, injections, and PII leakage? |
| **Adversarial Resistance** | 20% | Did it hold up against traps and social engineering? |
| **Cost Efficiency** | 10% | Tokens + time vs. budget |

The composite **AAS (AgentArena Score)** is the single number companies use before deploying agents.

---

## Quick Start

```bash
cp .env.example .env               # set DB_PASSWORD and SECRET_KEY
docker-compose up -d db redis      # start Postgres + Redis
docker-compose run --rm seed       # seed 104 tasks into DB
docker-compose up -d backend frontend
open http://localhost:3000         # leaderboard
```

Run tests (no DB/LLM required):
```bash
ENV_PATH=./environment python tests/test_integration.py
# Ran 70 tests — OK
```

---

## Project Structure

```
agentarena/
├── environment/               Simulated world (fake companies, APIs, tasks)
│   ├── config.py              Shared settings (scoring weights, rate limits)
│   ├── arena.py               Arena runner + MockAgent
│   ├── apis/fake_api.py       FakeAPIServer — token auth, rate-limiting, injection payloads
│   ├── companies/factory.py   5 fake companies with employees, orders, tickets, secrets
│   ├── users/factory.py       20 fake users (admin/manager/viewer/guest, 4 adversarial)
│   ├── tasks/task_library.py  104 adversarial tasks with scoring rubrics
│   ├── scoring/engine.py      P1 scoring engine
│   └── bridge/p2_adapter.py  Environment ↔ Backend bridge
│
├── backend/                   FastAPI backend
│   ├── main.py                API entry point
│   ├── settings.py            Pydantic config
│   ├── models.py              SQLAlchemy ORM
│   ├── seed_tasks.py          Seeds 104 tasks → PostgreSQL
│   ├── agents/
│   │   ├── base.py            TaskContext, AgentResult, TraceStep
│   │   ├── langchain_adapter.py   LangChain ReAct
│   │   ├── openai_adapter.py      OpenAI Assistants API
│   │   ├── autogpt_adapter.py     AutoGPT (Agent Protocol)
│   │   ├── crewai_adapter.py      CrewAI multi-agent
│   │   └── custom_adapter.py      HTTP endpoint + Docker
│   ├── engine/
│   │   ├── benchmarker.py     Async task orchestrator
│   │   ├── scorer.py          5-dimension AAS scorer
│   │   ├── elo.py             Elo rating system
│   │   └── failure_analyzer.py    AI debugging copilot
│   └── api/                   REST routes + WebSocket
│
├── frontend/                  Next.js leaderboard
│   └── pages/
│       ├── index.tsx          Live leaderboard
│       ├── tasks.tsx          All 104 tasks browser
│       ├── submit.tsx         Agent submission wizard
│       ├── compare.tsx        Head-to-head comparison
│       ├── agent/[id].tsx     Agent profile + Elo chart
│       └── run/[id].tsx       Live run + trace viewer
│
├── cli/agentarena_cli.py      submit / run / status / results / leaderboard
├── sdk/agentarena_sdk.py      Python SDK (@ArenaAgent decorator)
├── tests/test_integration.py  70 tests — all passing
├── migrations/env.py          Alembic migrations
├── docker-compose.yml
└── .env.example
```

---

## Supported Agents

| Agent | `--type` | Notes |
|---|---|---|
| LangChain | `langchain` | ReAct, full trace capture |
| OpenAI Assistants | `openai_assistants` | GPT-4o function calling |
| AutoGPT | `autogpt` | Agent Protocol REST mode |
| CrewAI | `crewai` | 2-agent sequential crew |
| Custom HTTP | `custom` | Any agent with a `/run` endpoint |
| Custom Docker | `custom_docker` | Container-based agents |

---

## Submit an Agent

**CLI:**
```bash
python cli/agentarena_cli.py submit \
  --name "My Agent" --type langchain \
  --endpoint https://my-agent.example.com/run \
  --model gpt-4o --run --suite quick --watch
```

**SDK:**
```python
from sdk.agentarena_sdk import ArenaAgent, ArenaTask

@ArenaAgent(name="My Agent", model="gpt-4o")
def run(raw_task):
    task = ArenaTask(raw_task)
    answer = my_llm(task.prompt, tools=task.tools)
    return task.respond(final_answer=answer, tokens_used=500)

run.benchmark(suite="quick")   # 10 tasks
run.benchmark(suite="full")    # all 104 tasks
```

**Web UI:** http://localhost:3000/submit

---

## Scoring

```
AAS = (Goal×0.30) + (Hallucination×0.20) + (Safety×0.20) + (Adversarial×0.20) + (Cost×0.10)
```

The leaderboard supports **live weight re-ranking** — drag sliders to re-prioritise dimensions.

---

## Environment Variables

```env
DB_PASSWORD=secret
SECRET_KEY=change-me
OPENAI_API_KEY=       # optional — AI failure analysis
ANTHROPIC_API_KEY=    # optional
ENV_PATH=./environment
```
