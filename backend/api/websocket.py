"""
WebSocket endpoint for live-streaming benchmark run progress.
Clients connect to /ws/runs/{run_id} and receive real-time events.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio
import json

router = APIRouter()

# ── Connection Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        # run_id -> set of connected WebSocket clients
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, run_id: str, ws: WebSocket):
        await ws.accept()
        if run_id not in self.connections:
            self.connections[run_id] = set()
        self.connections[run_id].add(ws)

    def disconnect(self, run_id: str, ws: WebSocket):
        if run_id in self.connections:
            self.connections[run_id].discard(ws)

    async def broadcast(self, run_id: str, event: str, data: dict):
        """Send an event to all clients watching this run."""
        message = json.dumps({"event": event, "data": data})
        dead = set()
        for ws in self.connections.get(run_id, set()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.connections[run_id].discard(ws)


manager = ConnectionManager()


@router.websocket("/runs/{run_id}")
async def run_progress(run_id: str, websocket: WebSocket):
    """
    WebSocket endpoint for live run progress.
    Emits events:
        run_started   — { run_id, total_tasks }
        task_started  — { run_id, task_id, title }
        task_completed — { run_id, task_id, status, aas }
        run_completed  — { run_id, aas }
        heartbeat      — { ts }
    """
    await manager.connect(run_id, websocket)
    try:
        while True:
            # Keep alive with periodic heartbeats
            await asyncio.sleep(15)
            await websocket.send_text(json.dumps({
                "event": "heartbeat",
                "data":  {"ts": asyncio.get_event_loop().time()}
            }))
    except WebSocketDisconnect:
        manager.disconnect(run_id, websocket)


async def emit_to_run(run_id: str, event: str, data: dict):
    """Called by BenchmarkEngine to push progress to connected clients."""
    await manager.broadcast(run_id, event, data)
