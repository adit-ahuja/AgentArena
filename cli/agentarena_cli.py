#!/usr/bin/env python3
"""
AgentArena CLI
Usage:
    agentarena submit --name "My Agent" --type langchain --endpoint https://...
    agentarena run    --agent-id <id> --suite full
    agentarena status --run-id <id>
    agentarena results --run-id <id>
    agentarena leaderboard
"""

import argparse
import sys
import json
import time
import os
import httpx
from typing import Optional


API_BASE = os.environ.get("ARENA_API_URL", "http://localhost:8000")

# ── ANSI colour helpers ────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
DIM    = "\033[2m"


def c(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}"


def banner():
    print(f"""
{BLUE}  ╔═══════════════════════════════╗
  ║  ⚔  AgentArena CLI  v1.0.0   ║
  ║  The AI Agent Benchmark       ║
  ╚═══════════════════════════════╝{RESET}
""")


# ── HTTP client ───────────────────────────────────────────────────────────────

def api(method: str, path: str, **kwargs) -> dict:
    url = f"{API_BASE}{path}"
    try:
        response = httpx.request(method, url, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        print(c(f"\n✗ Cannot connect to AgentArena API at {API_BASE}", RED))
        print(c("  Set ARENA_API_URL env var or start the backend.\n", DIM))
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(c(f"\n✗ API Error {e.response.status_code}: {e.response.text}\n", RED))
        sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_submit(args):
    """Submit an agent to AgentArena."""
    print(c("\n→ Submitting agent…", CYAN))

    payload = {
        "name":           args.name,
        "agent_type":     args.type,
        "version":        args.version or "1.0.0",
        "description":    args.description or "",
        "model_backbone": args.model or "",
        "config":         {},
    }

    if args.endpoint:
        payload["api_endpoint"] = args.endpoint
        payload["config"]["endpoint"] = args.endpoint

    if args.docker:
        payload["docker_image"] = args.docker

    agent = api("POST", "/api/agents/", json=payload)

    print(c(f"\n✓ Agent submitted successfully!", GREEN))
    print(f"  {c('ID:', DIM)} {agent['id']}")
    print(f"  {c('Name:', DIM)} {agent['name']}")
    print(f"  {c('Type:', DIM)} {agent['agent_type']}")
    print(f"  {c('Initial Elo:', DIM)} {agent['elo_rating']}")
    print(f"\n  {c('Run a benchmark:', YELLOW)} agentarena run --agent-id {agent['id']}\n")

    if args.run:
        args.agent_id = agent["id"]
        cmd_run(args)


def cmd_run(args):
    """Start a benchmark run."""
    suite = args.suite or "full"
    print(c(f"\n→ Starting {suite} benchmark run…", CYAN))

    run = api("POST", "/api/runs/", json={
        "agent_id":   args.agent_id,
        "task_suite": suite,
    })

    print(c(f"\n✓ Run queued!", GREEN))
    print(f"  {c('Run ID:', DIM)} {run['id']}")
    print(f"  {c('Status:', DIM)} {run['status']}")
    print(f"  {c('Suite:', DIM)} {suite}")
    print()

    if args.watch:
        _watch_run(run["id"])
    else:
        print(f"  Watch progress: {c(f'agentarena status --run-id {run[\"id\"]} --watch', YELLOW)}\n")


def _watch_run(run_id: str):
    """Poll a run until complete and print live progress."""
    print(c("  Watching run (Ctrl+C to detach)…\n", DIM))
    last_completed = -1

    while True:
        run     = api("GET", f"/api/runs/{run_id}")
        results = api("GET", f"/api/runs/{run_id}/results")

        if run["completed_tasks"] != last_completed:
            last_completed = run["completed_tasks"]
            bar = _progress_bar(run["completed_tasks"], run["total_tasks"])
            print(f"\r  {bar} {run['completed_tasks']}/{run['total_tasks']} tasks  ", end="", flush=True)

        if run["status"] in ("completed", "failed", "timeout"):
            print()
            _print_run_summary(run_id)
            break

        time.sleep(2)


def _progress_bar(done: int, total: int, width: int = 30) -> str:
    if total == 0:
        return "─" * width
    filled = int(width * done / total)
    bar    = "█" * filled + "░" * (width - filled)
    return f"{GREEN}{bar}{RESET}"


def cmd_status(args):
    """Check run status."""
    run = api("GET", f"/api/runs/{args.run_id}")

    status_color = {
        "completed": GREEN, "running": BLUE,
        "queued": YELLOW, "failed": RED, "timeout": RED,
    }.get(run["status"], DIM)

    print(f"\n  Run {c(args.run_id[:16], BOLD)}…")
    print(f"  Status:    {c(run['status'].upper(), status_color)}")
    print(f"  Progress:  {run['completed_tasks']} / {run['total_tasks']} tasks")
    print(f"  Tokens:    {run['total_tokens']:,}")
    print(f"  Cost:      ${run['total_cost_usd']:.4f}")
    print(f"  Wall time: {run['wall_time_secs']:.1f}s\n")

    if args.watch and run["status"] in ("queued", "running"):
        _watch_run(args.run_id)


def _print_run_summary(run_id: str):
    try:
        summary = api("GET", f"/api/runs/{run_id}/summary")
        score   = summary.get("score")
        run     = summary.get("run", {})

        print(f"\n  {c('═' * 50, DIM)}")
        print(f"  {c('BENCHMARK COMPLETE', GREEN)}\n")

        if score:
            aas = score["aas_score"]
            color = GREEN if aas >= 75 else YELLOW if aas >= 50 else RED
            print(f"  {BOLD}AAS Score: {c(f'{aas:.1f}/100', color)}{RESET}")
            print()
            print(f"  {'Goal Completion':20s} {_score_bar(score['goal_completion_avg'])} {score['goal_completion_avg']:.1f}")
            print(f"  {'Anti-Hallucination':20s} {_score_bar(score['hallucination_avg'])}   {score['hallucination_avg']:.1f}")
            print(f"  {'Safety':20s} {_score_bar(score['safety_avg'])}   {score['safety_avg']:.1f}")
            print(f"  {'Adversarial Resist':20s} {_score_bar(score['adversarial_avg'])}   {score['adversarial_avg']:.1f}")
            print(f"  {'Cost Efficiency':20s} {_score_bar(score['cost_avg'])}   {score['cost_avg']:.1f}")
            print()
            print(f"  Pass rate:  {score['pass_rate']:.1f}%")
            print(f"  Elo:        {score.get('elo_after', run.get('elo_rating', '—'))}")

        print(f"\n  Total cost: ${run.get('total_cost_usd', 0):.4f}")
        print(f"  Tokens:     {run.get('total_tokens', 0):,}")
        print()
        print(f"  {c('View full report:', YELLOW)} {API_BASE.replace(':8000', ':3000')}/run/{run_id}")
        print(f"  {c('═' * 50, DIM)}\n")

    except Exception:
        print(c(f"\n  Run {run_id[:16]}… completed.\n", GREEN))


def _score_bar(val: float, width: int = 20) -> str:
    filled = int(width * val / 100)
    color  = GREEN if val >= 75 else YELLOW if val >= 50 else RED
    bar    = "█" * filled + "░" * (width - filled)
    return f"{color}{bar}{RESET}"


def cmd_results(args):
    """Print task-level results for a run."""
    results = api("GET", f"/api/runs/{args.run_id}/results")
    print(f"\n  {c('Task Results', BOLD)} ({len(results)} tasks)\n")

    for r in results[:args.limit or 20]:
        status_sym = {"pass": f"{GREEN}✓{RESET}", "partial": f"{YELLOW}~{RESET}",
                      "fail": f"{RED}✗{RESET}", "timeout": f"{RED}T{RESET}"}.get(r["status"], "?")
        print(f"  {status_sym}  {r['task_id'][:8]}…  "
              f"goal={c(str(round(r.get('goal_completion_score') or 0)), GREEN)}  "
              f"tok={r['tokens_used']}  t={r['time_seconds']:.1f}s")

        if r["failure_reasons"] and args.verbose:
            for reason in r["failure_reasons"]:
                print(f"      {c('↳', RED)} {reason}")

        if r.get("ai_analysis") and args.verbose:
            print(f"      {c('AI:', BLUE)} {r['ai_analysis'][:120]}…")

    print()


def cmd_leaderboard(args):
    """Print the current leaderboard."""
    entries = api("GET", f"/api/leaderboard/", params={"limit": args.limit or 10})
    print(f"\n  {c('⚔ AgentArena Leaderboard', BOLD)}\n")
    print(f"  {'#':3}  {'Agent':25} {'AAS':6} {'Elo':6}  {'Pass%':6}")
    print(f"  {DIM}{'─' * 52}{RESET}")

    for e in entries:
        rank_sym = ["🥇", "🥈", "🥉"][e["rank"] - 1] if e["rank"] <= 3 else f" {e['rank']}."
        verified = c("✓", BLUE) if e["is_verified"] else " "
        aas_color = GREEN if e["aas_score"] >= 75 else YELLOW if e["aas_score"] >= 50 else RED
        print(
            f"  {rank_sym}  {verified} {e['agent_name'][:22]:22}  "
            f"{c(f'{e[\"aas_score\"]:5.1f}', aas_color)}  "
            f"{c(str(round(e[\"elo_rating\"])), YELLOW):6}  "
            f"{e['pass_rate']:.0f}%"
        )

    print()


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    banner()
    parser = argparse.ArgumentParser(prog="agentarena", description="AgentArena CLI")
    sub    = parser.add_subparsers(dest="command")

    # submit
    p_sub = sub.add_parser("submit", help="Submit an agent")
    p_sub.add_argument("--name",        required=True, help="Agent display name")
    p_sub.add_argument("--type",        required=True,
                       choices=["langchain","openai_assistants","autogpt","crewai","custom"],
                       help="Agent type")
    p_sub.add_argument("--endpoint",    help="HTTP endpoint URL")
    p_sub.add_argument("--docker",      help="Docker image name")
    p_sub.add_argument("--model",       help="Model backbone (e.g. gpt-4o)")
    p_sub.add_argument("--version",     default="1.0.0")
    p_sub.add_argument("--description", help="Agent description")
    p_sub.add_argument("--run",         action="store_true", help="Auto-run after submit")
    p_sub.add_argument("--suite",       default="full",
                       choices=["full","quick","adversarial"])

    # run
    p_run = sub.add_parser("run", help="Start a benchmark run")
    p_run.add_argument("--agent-id",    required=True, dest="agent_id")
    p_run.add_argument("--suite",       default="full",
                       choices=["full","quick","adversarial"])
    p_run.add_argument("--watch",       action="store_true", help="Stream progress")

    # status
    p_st = sub.add_parser("status", help="Check run status")
    p_st.add_argument("--run-id", required=True, dest="run_id")
    p_st.add_argument("--watch",  action="store_true")

    # results
    p_res = sub.add_parser("results", help="Print task results")
    p_res.add_argument("--run-id",  required=True, dest="run_id")
    p_res.add_argument("--limit",   type=int, default=20)
    p_res.add_argument("--verbose", action="store_true")

    # leaderboard
    p_lb = sub.add_parser("leaderboard", help="Show the leaderboard")
    p_lb.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    dispatch = {
        "submit":      cmd_submit,
        "run":         cmd_run,
        "status":      cmd_status,
        "results":     cmd_results,
        "leaderboard": cmd_leaderboard,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
