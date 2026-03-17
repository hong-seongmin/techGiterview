from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

SELECTOR_RUBRIC_KEYS = [
    "runtime_relevance",
    "architecture_coverage",
    "config_coverage",
    "noise_control",
    "explanation_quality",
]
QUESTION_SET_RUBRIC_KEYS = [
    "groundedness",
    "repo_specificity",
    "technical_correctness",
    "interview_usefulness",
    "set_diversity",
]
SELECTOR_AUTO_FAIL_TAGS = {"docs_contamination", "test_contamination", "missed_entrypoint"}
QUESTION_AUTO_FAIL_TAGS = {"hallucinated_architecture", "ungrounded"}


def _normalized_scores(scores: dict[str, Any], required_keys: list[str]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for key in required_keys:
        value = scores.get(key)
        if value is None:
            raise ValueError(f"Missing required score: {key}")
        normalized[key] = float(value)
    return normalized


def evaluate_selector_review(scores: dict[str, Any], failure_tags: list[str]) -> dict[str, Any]:
    normalized = _normalized_scores(scores, SELECTOR_RUBRIC_KEYS)
    overall_score = round(mean(normalized.values()), 2)
    passed = (
        overall_score >= 4.0
        and all(score >= 3.0 for score in normalized.values())
        and not (set(failure_tags) & SELECTOR_AUTO_FAIL_TAGS)
    )
    return {
        "passed": passed,
        "overall_score": overall_score,
        "scores": normalized,
        "failure_tags": failure_tags,
    }


def evaluate_question_review(
    set_scores: dict[str, Any],
    question_reviews: list[dict[str, Any]],
    failure_tags: list[str],
) -> dict[str, Any]:
    normalized = _normalized_scores(set_scores, QUESTION_SET_RUBRIC_KEYS)
    overall_score = round(mean(normalized.values()), 2)
    question_scores = [float(item.get("score", 0.0)) for item in question_reviews]
    passed = (
        overall_score >= 4.0
        and all(score >= 3.0 for score in normalized.values())
        and all(score >= 3.0 for score in question_scores)
        and not (set(failure_tags) & QUESTION_AUTO_FAIL_TAGS)
        and not any(set(item.get("failure_tags", [])) & QUESTION_AUTO_FAIL_TAGS for item in question_reviews)
    )
    return {
        "passed": passed,
        "overall_score": overall_score,
        "set_scores": normalized,
        "question_reviews": question_reviews,
        "failure_tags": failure_tags,
    }


def build_failure_histogram(reviews: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for review in reviews:
        counter.update(review.get("failure_tags", []))
        for question_review in review.get("question_reviews", []):
            counter.update(question_review.get("failure_tags", []))
    return dict(counter)


def decide_next_target(selector_reviews: list[dict[str, Any]], question_reviews: list[dict[str, Any]]) -> dict[str, Any]:
    selector_fail_count = sum(1 for review in selector_reviews if not review.get("passed", False))
    question_fail_count = sum(1 for review in question_reviews if not review.get("passed", False))
    selector_total = len(selector_reviews) or 1
    question_total = len(question_reviews) or 1
    selector_fail_rate = selector_fail_count / selector_total
    question_fail_rate = question_fail_count / question_total

    if selector_fail_rate >= 0.3 and question_fail_rate >= 0.3:
        next_target = "selector"
        reason = "selector_fail_rate>=0.3 and question_fail_rate>=0.3; selector를 먼저 수정"
    elif selector_fail_rate >= 0.3:
        next_target = "selector"
        reason = "selector_fail_rate>=0.3"
    elif question_fail_rate >= 0.3:
        next_target = "generator"
        reason = "question_fail_rate>=0.3"
    else:
        next_target = "joint"
        reason = "selector/question fail rate 모두 0.3 미만"

    return {
        "next_target": next_target,
        "selector_fail_rate": round(selector_fail_rate, 3),
        "question_fail_rate": round(question_fail_rate, 3),
        "reason": reason,
    }
