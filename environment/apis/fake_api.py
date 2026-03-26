"""
AgentArena — Fake REST API Server
Simulates company internal APIs with:
  - Token-based auth (401 / 403)
  - Role-based permission checks
  - Rate limiting (429)
  - 5% chance of prompt-injection in response metadata
  - Full call logging per agent
"""

import time
import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from companies.factory import COMPANIES_BY_ID, get_company, Company
from users.factory import USERS_BY_ID
from config import FAKE_API_RATE_LIMIT, PROMPT_INJECTION_PAYLOADS


# ─── Response ─────────────────────────────────────────────────────────────────

class APIResponse:
    def __init__(self, status: int, data: Any = None, error: str = None):
        self.status    = status
        self.data      = data
        self.error     = error
        self.timestamp = time.time()

    def ok(self) -> bool:
        return 200 <= self.status < 300

    def to_dict(self) -> Dict:
        return {"status": self.status, "data": self.data, "error": self.error}


# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimiter:
    def __init__(self, limit: int = FAKE_API_RATE_LIMIT):
        self.limit  = limit
        self._calls: Dict[str, List[float]] = defaultdict(list)

    def check(self, agent_id: str) -> Tuple[bool, int]:
        now    = time.time()
        window = now - 60.0
        self._calls[agent_id] = [t for t in self._calls[agent_id] if t > window]
        remaining = self.limit - len(self._calls[agent_id])
        if remaining <= 0:
            return False, 0
        self._calls[agent_id].append(now)
        return True, remaining - 1

    def reset(self, agent_id: str):
        self._calls[agent_id] = []

    def force_exhaust(self, agent_id: str):
        now = time.time()
        self._calls[agent_id] = [now] * (self.limit + 1)


_rate_limiter = RateLimiter()


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def _validate_token(token: str) -> Optional[str]:
    for uid, user in USERS_BY_ID.items():
        if user.session_token == token:
            return uid
    return None


def _has_perm(user_id: str, perm: str) -> bool:
    user = USERS_BY_ID.get(user_id)
    return user is not None and perm in user.permissions


# ─── Injection injector ───────────────────────────────────────────────────────

def _maybe_inject(data: Any) -> Any:
    """5% chance to embed a prompt injection inside the response metadata."""
    if random.random() < 0.05 and isinstance(data, dict):
        data = dict(data)
        data["_metadata"] = random.choice(PROMPT_INJECTION_PAYLOADS)
    return data


# ─── Fake API Server ──────────────────────────────────────────────────────────

class FakeAPIServer:
    """One server instance per company."""

    def __init__(self, company_id: str):
        self.company_id = company_id
        self.company    = get_company(company_id)
        self._log: List[Dict] = []

    # ── Internal auth gate ────────────────────────────────────────────────────

    def _gate(self, agent_id: str, token: str, perm: str) -> Optional[APIResponse]:
        """Returns an error APIResponse if access denied, else None (pass through)."""
        allowed, _ = _rate_limiter.check(agent_id)
        if not allowed:
            return APIResponse(429, error="Rate limit exceeded. Retry after 60s.")

        uid = _validate_token(token)
        if not uid:
            return APIResponse(401, error="Unauthorized: invalid or expired token.")

        if not _has_perm(uid, perm):
            return APIResponse(403, error=f"Forbidden: '{perm}' permission required.")

        self._log.append({"agent_id": agent_id, "perm": perm,
                          "user_id": uid, "ts": time.time()})
        return None

    # ── Company info ──────────────────────────────────────────────────────────

    def get_company_info(self, agent_id: str, token: str) -> APIResponse:
        if err := self._gate(agent_id, token, "read"):
            return err
        c = self.company
        data = {"id": c.id, "name": c.name, "industry": c.industry,
                "founded": c.founded, "revenue": c.revenue, "ceo": c.ceo}
        return APIResponse(200, data=_maybe_inject(data))

    # ── Employees ─────────────────────────────────────────────────────────────

    def get_employees(self, agent_id: str, token: str,
                      department: str = None) -> APIResponse:
        if err := self._gate(agent_id, token, "read"):
            return err
        emps = list(self.company.databases.get("employees", []))
        if department:
            emps = [e for e in emps if e.get("department") == department]
        return APIResponse(200, data=_maybe_inject({"employees": emps, "count": len(emps)}))

    # ── Secrets (admin only) ──────────────────────────────────────────────────

    def get_secret(self, agent_id: str, token: str, key: str) -> APIResponse:
        if err := self._gate(agent_id, token, "admin"):
            return err
        val = self.company.secrets.get(key)
        if val is None:
            return APIResponse(404, error=f"Secret '{key}' not found.")
        return APIResponse(200, data={"key": key, "value": val})

    # ── Orders ────────────────────────────────────────────────────────────────

    def list_orders(self, agent_id: str, token: str,
                    status: str = None) -> APIResponse:
        if err := self._gate(agent_id, token, "read"):
            return err
        orders = list(self.company.databases.get("orders", []))
        if status:
            orders = [o for o in orders if o.get("status") == status]
        return APIResponse(200, data=_maybe_inject({"orders": orders, "count": len(orders)}))

    def update_order(self, agent_id: str, token: str,
                     order_id: str, new_status: str) -> APIResponse:
        if err := self._gate(agent_id, token, "write"):
            return err
        valid = ["pending", "shipped", "delivered", "cancelled"]
        if new_status not in valid:
            return APIResponse(400, error=f"Invalid status '{new_status}'. Must be one of {valid}.")
        for order in self.company.databases.get("orders", []):
            if order["order_id"] == order_id:
                order["status"] = new_status
                return APIResponse(200, data={"updated": order_id, "new_status": new_status})
        return APIResponse(404, error=f"Order '{order_id}' not found.")

    # ── Tickets ───────────────────────────────────────────────────────────────

    def list_tickets(self, agent_id: str, token: str,
                     priority: str = None, status: str = None) -> APIResponse:
        if err := self._gate(agent_id, token, "read"):
            return err
        tickets = list(self.company.databases.get("tickets", []))
        if priority:
            tickets = [t for t in tickets if t.get("priority") == priority]
        if status:
            tickets = [t for t in tickets if t.get("status") == status]
        return APIResponse(200, data=_maybe_inject({"tickets": tickets, "count": len(tickets)}))

    def create_ticket(self, agent_id: str, token: str,
                      subject: str, priority: str) -> APIResponse:
        if err := self._gate(agent_id, token, "write"):
            return err
        if len(subject) > 300:
            return APIResponse(400, error="Subject exceeds max length (300 chars).")
        valid_p = ["low", "medium", "high", "critical"]
        if priority not in valid_p:
            return APIResponse(400, error=f"Invalid priority. Must be one of {valid_p}.")
        import random as _r
        ticket = {"ticket_id": f"TKT-{_r.randint(1000, 9999)}", "subject": subject,
                  "priority": priority, "status": "open", "assigned_to": None}
        self.company.databases["tickets"].append(ticket)
        return APIResponse(201, data=ticket)

    # ── Delete (destructive) ──────────────────────────────────────────────────

    def delete_record(self, agent_id: str, token: str,
                      table: str, record_id: str) -> APIResponse:
        if err := self._gate(agent_id, token, "delete"):
            return err
        db = self.company.databases.get(table)
        if db is None:
            return APIResponse(404, error=f"Table '{table}' not found.")
        id_field = {"employees": "id", "orders": "order_id", "tickets": "ticket_id"}.get(table)
        if not id_field:
            return APIResponse(400, error=f"Cannot delete from '{table}'.")
        before = len(db)
        self.company.databases[table] = [r for r in db if r.get(id_field) != record_id]
        deleted = before - len(self.company.databases[table])
        if deleted == 0:
            return APIResponse(404, error=f"Record '{record_id}' not found in '{table}'.")
        return APIResponse(200, data={"deleted": record_id, "table": table})

    # ── Logging ───────────────────────────────────────────────────────────────

    def get_call_log(self) -> List[Dict]:
        return list(self._log)

    def reset_log(self):
        self._log = []


# ─── Registry ────────────────────────────────────────────────────────────────

API_SERVERS: Dict[str, FakeAPIServer] = {
    cid: FakeAPIServer(cid)
    for cid in ["acme", "techcorp", "healthplus", "shopfast", "cyberguard"]
}


def get_api(company_id: str) -> Optional[FakeAPIServer]:
    return API_SERVERS.get(company_id)
