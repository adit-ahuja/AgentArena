# AgentArena — Deployment Guide

## Option A — Docker (Recommended)

### 1. Configure
```bash
cp .env.example .env
# Edit .env: set DB_PASSWORD and SECRET_KEY
# Optional: add OPENAI_API_KEY or ANTHROPIC_API_KEY for AI failure analysis
```

### 2. Start infrastructure
```bash
docker-compose up -d db redis
# Wait ~5s then verify: docker-compose ps → db "healthy"
```

### 3. Seed 104 tasks
```bash
docker-compose run --rm seed
# → [seed] ✓ 104 tasks seeded
```

### 4. Start the app
```bash
docker-compose up -d backend frontend
```

### 5. Verify
```bash
curl http://localhost:8000/health           # {"status":"ok"}
curl http://localhost:8000/api/tasks/ | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'tasks')"
open http://localhost:3000                  # leaderboard
```

### 6. Run tests
```bash
ENV_PATH=./environment python tests/test_integration.py
# Ran 70 tests — OK
```

---

## Option B — Local Development

```bash
# Python env
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt

# Start infra
docker-compose up -d db redis

# Set env vars
export DATABASE_URL="postgresql://agentarena:secret@localhost:5432/agentarena"
export REDIS_URL="redis://localhost:6379"
export SECRET_KEY="dev-secret"
export ENV_PATH="$(pwd)/environment"
export PYTHONPATH="$(pwd)/environment:$(pwd)/backend"

# Seed
python backend/seed_tasks.py

# Backend
cd backend && uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

---

## Submit an Agent

### CLI
```bash
python cli/agentarena_cli.py submit \
  --name "My Agent" --type langchain \
  --endpoint https://my-agent.example.com/run \
  --model gpt-4o --run --suite quick --watch
```

### SDK
```python
from sdk.agentarena_sdk import ArenaAgent, ArenaTask

@ArenaAgent(name="My Agent", model="gpt-4o")
def run(raw_task):
    task = ArenaTask(raw_task)
    return task.respond(final_answer=my_llm(task.prompt), tokens_used=500)

run.benchmark(suite="quick")
```

### AutoGPT
```bash
# Start AutoGPT in API mode first:
python autogpt --enable-api --api-port 8080

# Then submit:
python cli/agentarena_cli.py submit --name "AutoGPT" --type autogpt \
  --endpoint http://localhost:8080 --run --suite quick
```

### CrewAI
```bash
pip install crewai crewai-tools
python cli/agentarena_cli.py submit --name "CrewAI" --type crewai \
  --model gpt-4o --run --suite quick
```

### Custom HTTP Agent Protocol

Your `/run` endpoint must accept:
```json
{
  "task_id": "T042",
  "prompt": "...",
  "environment": {"tools": [{"name": "...", "description": "...", "response": {...}}]},
  "max_tokens": 2000,
  "timeout_seconds": 90
}
```
And return:
```json
{"final_answer": "...", "trace": [...], "tokens_used": 50, "cost_usd": 0.0001}
```

---

## Run Benchmarks

```bash
python cli/agentarena_cli.py run --agent-id <id> --suite quick      --watch  # 10 tasks
python cli/agentarena_cli.py run --agent-id <id> --suite full       --watch  # 104 tasks
python cli/agentarena_cli.py run --agent-id <id> --suite adversarial --watch # 64 adversarial

python cli/agentarena_cli.py results     --run-id <id> --verbose
python cli/agentarena_cli.py leaderboard
```

---

## Production Checklist

```bash
# 1. Change secrets in .env
DB_PASSWORD=<strong-random-password>
SECRET_KEY=<32-char-random-string>

# 2. Set LLM key for AI failure analysis
OPENAI_API_KEY=sk-...

# 3. Set frontend to production backend URL
NEXT_PUBLIC_API_URL=https://api.yourdomain.com

# 4. Add Nginx + TLS in front of :8000 and :3000

# 5. Postgres backup
pg_dump agentarena > backup_$(date +%Y%m%d).sql
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `No module named 'pydantic_settings'` | `pip install pydantic-settings==2.3.0` |
| `No module named 'tasks'` | `export ENV_PATH=./environment PYTHONPATH=./environment:./backend` |
| `connection refused :5432` | `docker-compose up -d db` and wait for healthcheck |
| Tasks table empty | Run `python backend/seed_tasks.py` with `ENV_PATH` set |
| Frontend shows demo data | Backend not running — `docker-compose up -d backend` |
| AutoGPT connection refused | `python autogpt --enable-api --api-port 8080` |
