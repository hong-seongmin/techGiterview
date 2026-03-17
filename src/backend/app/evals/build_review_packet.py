from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.evals.workflow import build_review_packet_payload, write_review_packet_files


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build manual review packet files for an iteration.")
    parser.add_argument("--iteration-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db = SessionLocal()
    try:
        payload = build_review_packet_payload(db, args.iteration_id)
    finally:
        db.close()

    paths = write_review_packet_files(args.iteration_id, payload)
    print(f"selector_template={paths['selector_template']}")
    print(f"question_template={paths['question_template']}")
    print(f"review_packet={paths['review_packet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
