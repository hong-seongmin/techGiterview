from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

from app.core.database import SessionLocal
from app.evals.common import DEFAULT_CANARY_DAILY_CAP, DEFAULT_MIXED_BENCHMARK_COUNT, DEFAULT_MIXED_RECENT_COUNT
from app.models.repository import RepositoryAnalysis


@dataclass
class DatasetItem:
    repo_url: str
    source: str
    cohort: str
    tags: list[str] = field(default_factory=list)
    analysis_id: str | None = None
    repository_name: str | None = None
    repository_owner: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_repo_url(repo_url: str) -> str:
    return repo_url.rstrip("/").lower()


def build_mixed_iteration_dataset(
    benchmark_items: Iterable[dict[str, Any]],
    recent_items: Iterable[dict[str, Any]],
    *,
    benchmark_primary_count: int = DEFAULT_MIXED_BENCHMARK_COUNT,
    recent_target_count: int = DEFAULT_MIXED_RECENT_COUNT,
) -> list[dict[str, Any]]:
    benchmark_primary: list[dict[str, Any]] = []
    benchmark_reserve: list[dict[str, Any]] = []
    for item in benchmark_items:
        cohort = item.get("cohort", "primary")
        if cohort == "primary":
            benchmark_primary.append(dict(item))
        else:
            benchmark_reserve.append(dict(item))

    selected_primary = benchmark_primary[:benchmark_primary_count]
    seen_urls = {_normalize_repo_url(item["repo_url"]) for item in selected_primary}

    selected_recent: list[dict[str, Any]] = []
    for item in recent_items:
        normalized = _normalize_repo_url(item["repo_url"])
        if normalized in seen_urls:
            continue
        selected_recent.append(dict(item))
        seen_urls.add(normalized)
        if len(selected_recent) >= recent_target_count:
            break

    if len(selected_recent) < recent_target_count:
        for item in benchmark_reserve:
            normalized = _normalize_repo_url(item["repo_url"])
            if normalized in seen_urls:
                continue
            reserve_item = dict(item)
            reserve_item["source"] = "benchmark_reserve"
            selected_recent.append(reserve_item)
            seen_urls.add(normalized)
            if len(selected_recent) >= recent_target_count:
                break

    return selected_primary + selected_recent


def build_canary_iteration_dataset(
    recent_items: Iterable[dict[str, Any]],
    *,
    daily_cap: int = DEFAULT_CANARY_DAILY_CAP,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in recent_items:
        normalized = _normalize_repo_url(item["repo_url"])
        if normalized in seen_urls:
            continue
        selected.append(dict(item))
        seen_urls.add(normalized)
        if len(selected) >= daily_cap:
            break
    return selected


def load_recent_analysis_dataset(*, days: int = 14, limit: int = 50) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.query(RepositoryAnalysis)
            .filter(RepositoryAnalysis.status == "completed")
            .order_by(RepositoryAnalysis.created_at.desc())
            .limit(limit)
            .all()
        )

        dataset: list[dict[str, Any]] = []
        for row in rows:
            created_at = row.created_at
            if created_at and created_at.replace(tzinfo=None) < cutoff:
                continue
            repo_url = row.repository_url
            if not repo_url:
                continue
            metadata = row.analysis_metadata if isinstance(row.analysis_metadata, dict) else {}
            selector_experiment = metadata.get("selector_experiment", {})
            dataset.append(
                DatasetItem(
                    repo_url=repo_url,
                    source="recent_analysis",
                    cohort="recent",
                    tags=[row.primary_language or "unknown"],
                    analysis_id=str(row.id),
                    repository_name=row.repository_name,
                    created_at=created_at.isoformat() if created_at else None,
                    repository_owner=(repo_url.replace("https://github.com/", "").split("/")[0] if repo_url else None),
                ).to_dict()
            )
        return dataset
    finally:
        db.close()
