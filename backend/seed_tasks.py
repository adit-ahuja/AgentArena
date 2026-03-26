"""
AgentArena — Unified Task Seeder
Pulls all 104 tasks from Person 1's task_library and seeds Person 2's PostgreSQL DB.

Usage:
    cd backend
    python seed_tasks.py                  # seed from P1 library (default)
    python seed_tasks.py --overwrite      # overwrite existing tasks
    python seed_tasks.py --dry-run        # print what would be seeded
"""

import sys, os, argparse, json

# ── Put P1 on the path ────────────────────────────────────────────────────────
ENV_PATH = os.environ.get("ENV_PATH", os.path.join(os.path.dirname(__file__), "../environment"))
sys.path.insert(0, ENV_PATH)

from db.database import SessionLocal, Base, engine
import models

# ── Category mapping: P1 names → P2 TaskCategory enum values ─────────────────
CATEGORY_MAP = {
    "data_retrieval": "tool_use",
    "write":          "multi_step",
    "multi_step":     "multi_step",
    "adversarial":    "adversarial",
}


def load_p1_tasks():
    """Import all 104 tasks from P1's task_library."""
    from tasks.task_library import TASK_CATALOGUE
    return TASK_CATALOGUE


def task_to_model(t) -> dict:
    """Convert a P1 Task dataclass to a dict for P2's models.Task."""
    return dict(
        slug                 = t.id,
        title                = t.name,
        description          = t.description,
        category             = CATEGORY_MAP.get(t.category, t.category),
        difficulty           = t.difficulty,
        prompt               = t.prompt or t.description,
        environment          = t.environment  or {},
        expected_outcome     = t.expected_outcome or {},
        adversarial_elements = t.adversarial_elements or [],
        scoring_rubric       = t.scoring_rubric or {},
        max_tokens           = t.max_tokens,
        timeout_seconds      = t.timeout_seconds,
        is_public            = t.is_public,
    )


def seed(overwrite: bool = False, dry_run: bool = False) -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        tasks = load_p1_tasks()
        existing = {r.slug for r in db.query(models.Task.slug).all()}
        count = 0

        for t in tasks:
            d = task_to_model(t)
            slug = d["slug"]

            if dry_run:
                action = "UPDATE" if slug in existing else "INSERT"
                print(f"  [{action}] {slug:6s}  {d['difficulty']:12s}  {t.category}")
                count += 1
                continue

            if slug in existing:
                if not overwrite:
                    continue
                row = db.query(models.Task).filter_by(slug=slug).first()
                for k, v in d.items():
                    setattr(row, k, v)
            else:
                db.add(models.Task(**d))

            count += 1

        if not dry_run:
            db.commit()
            print(f"[seed] ✓ {count} tasks seeded "
                  f"({'overwrite' if overwrite else 'insert-only'}, "
                  f"{len(existing)} already existed).")
        else:
            print(f"[seed] Dry-run: would process {count} tasks.")

        return count
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run",   action="store_true")
    args = parser.parse_args()
    seed(overwrite=args.overwrite, dry_run=args.dry_run)
