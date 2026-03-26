"""
AgentArena — Backend API
The world's first adversarial battleground for AI agents.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from db.database import engine, Base
from api import agents, runs, leaderboard, tasks, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="AgentArena API",
    description="The world's first adversarial battleground for AI agents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router,      prefix="/api/agents",      tags=["Agents"])
app.include_router(runs.router,        prefix="/api/runs",        tags=["Runs"])
app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["Leaderboard"])
app.include_router(tasks.router,       prefix="/api/tasks",       tags=["Tasks"])
app.include_router(websocket.router,   prefix="/ws",              tags=["WebSocket"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "AgentArena API v1.0.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
