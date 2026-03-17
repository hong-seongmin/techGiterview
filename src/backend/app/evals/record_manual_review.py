from __future__ import annotations

import argparse
from pathlib import Path

from app.core.database import Base, SessionLocal, engine
from app.evals.common import read_json
from app.evals.workflow import upsert_question_manual_review, upsert_selector_manual_review


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import manual review JSON into the database.")
    parser.add_argument("--input", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = read_json(args.input)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    try:
        selector_count = 0
        question_count = 0
        iteration_id = payload["iteration_id"]
        for review in payload.get("selector_reviews", []):
            upsert_selector_manual_review(
                db,
                file_selection_run_id=review["file_selection_run_id"],
                iteration_id=iteration_id,
                reviewer=review["reviewer"],
                scores_json=review["scores_json"],
                failure_tags=list(review.get("failure_tags", [])),
                notes=review.get("notes"),
            )
            selector_count += 1

        for review in payload.get("question_reviews", []):
            upsert_question_manual_review(
                db,
                question_generation_run_id=review["question_generation_run_id"],
                iteration_id=iteration_id,
                reviewer=review["reviewer"],
                set_scores_json=review["set_scores_json"],
                question_reviews_json=list(review.get("question_reviews_json", [])),
                failure_tags=list(review.get("failure_tags", [])),
                notes=review.get("notes"),
            )
            question_count += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"iteration_id={payload['iteration_id']}")
    print(f"selector_reviews_imported={selector_count}")
    print(f"question_reviews_imported={question_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
