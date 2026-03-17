from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.evals.workflow import summarize_iteration_to_payload, write_iteration_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize manual review results for an iteration.")
    parser.add_argument("--iteration-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db = SessionLocal()
    try:
        payload = summarize_iteration_to_payload(db, args.iteration_id)
    finally:
        db.close()

    summary_path = write_iteration_summary(args.iteration_id, payload)
    print(f"summary_path={summary_path}")
    print(f"fully_passed={payload['fully_passed']}")
    print(f"promotion_ready={payload['promotion_ready']}")
    print(f"next_target={payload['decision']['next_target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
