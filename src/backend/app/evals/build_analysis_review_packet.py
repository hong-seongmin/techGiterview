from __future__ import annotations

import argparse
import uuid

from sqlalchemy import desc

from app.core.database import SessionLocal
from app.evals.workflow import (
    build_review_packet_payload_for_analysis_ids,
    write_review_packet_files,
)
from app.models.repository import RepositoryAnalysis


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build manual review packet files for explicit analysis ids or latest analyses per repo."
    )
    parser.add_argument("--analysis-id", action="append", default=[])
    parser.add_argument("--repo-url", action="append", default=[])
    parser.add_argument("--label", default="analysis-review")
    return parser.parse_args(argv)


def _resolve_analysis_ids(db, args: argparse.Namespace) -> list[str]:
    analysis_ids: list[str] = []

    for raw_analysis_id in args.analysis_id:
        analysis_ids.append(str(uuid.UUID(str(raw_analysis_id))))

    for repo_url in args.repo_url:
        analysis = (
            db.query(RepositoryAnalysis)
            .filter(RepositoryAnalysis.repository_url == repo_url)
            .order_by(desc(RepositoryAnalysis.created_at))
            .first()
        )
        if analysis is not None:
            analysis_ids.append(str(analysis.id))

    unique_ids: list[str] = []
    seen = set()
    for analysis_id in analysis_ids:
        if analysis_id in seen:
            continue
        unique_ids.append(analysis_id)
        seen.add(analysis_id)
    return unique_ids


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db = SessionLocal()
    try:
        analysis_ids = _resolve_analysis_ids(db, args)
        if not analysis_ids:
            raise SystemExit("No analyses found for the provided inputs.")
        payload = build_review_packet_payload_for_analysis_ids(
            db,
            analysis_ids,
            label=args.label,
        )
    finally:
        db.close()

    paths = write_review_packet_files(args.label, payload)
    print(f"analysis_count={len(analysis_ids)}")
    print(f"selector_template={paths['selector_template']}")
    print(f"question_template={paths['question_template']}")
    print(f"review_packet={paths['review_packet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
