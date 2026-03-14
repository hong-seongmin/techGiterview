from typing import Any, Iterable, Optional

from app.services.flow_graph_analyzer import FlowGraphAnalyzer


def build_analysis_graph_response(
    key_files: Iterable[Any],
    repo_name: Optional[str] = None,
) -> dict[str, Any]:
    """Build a graph API payload from analysis key files."""
    file_map: dict[str, str] = {}
    metadata_map: dict[str, dict[str, Any]] = {}

    for raw_file in key_files or []:
        if isinstance(raw_file, dict):
            path = raw_file.get("path")
            content = raw_file.get("content")
            score = raw_file.get("importance_score")
            reason = raw_file.get("selection_reason") or raw_file.get("reason") or ""
            importance = raw_file.get("importance") or "medium"
        else:
            path = getattr(raw_file, "path", None)
            content = getattr(raw_file, "content", None)
            score = getattr(raw_file, "importance_score", None)
            reason = getattr(raw_file, "selection_reason", "") or getattr(raw_file, "reason", "") or ""
            importance = getattr(raw_file, "importance", None) or "medium"

        if not path:
            continue

        if content:
            file_map[path] = content

        metadata_map[path] = {
            "importance_score": float(score) if score is not None else 0.0,
            "selection_reason": reason,
            "importance_level": importance,
        }

    if not file_map:
        return {
            "state": "empty",
            "message": "핵심 파일 간 분석 가능한 의존성 관계를 찾지 못했습니다.",
            "nodes": [],
            "links": [],
        }

    analyzer = FlowGraphAnalyzer()
    graph = analyzer.build_graph(file_map, repo_name=repo_name)

    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    for node, attrs in graph.nodes(data=True):
        node_type = attrs.get("type", "unknown")
        if hasattr(node_type, "value"):
            node_type = node_type.value

        meta = metadata_map.get(node, {})
        score = meta.get("importance_score", 0)
        visual_score = score if score > 0 else attrs.get("density", 0.1)

        nodes.append(
            {
                "id": node,
                "name": node.split("/")[-1],
                "val": visual_score,
                "type": node_type,
                "density": attrs.get("density", 0),
                "reason": meta.get("selection_reason", ""),
                "importance": meta.get("importance_level", "medium"),
            }
        )

    for source, target, attrs in graph.edges(data=True):
        links.append(
            {
                "source": source,
                "target": target,
                "type": attrs.get("type", "dependency"),
            }
        )

    if not nodes:
        return {
            "state": "empty",
            "message": "핵심 파일 간 분석 가능한 의존성 관계를 찾지 못했습니다.",
            "nodes": [],
            "links": [],
        }

    return {
        "state": "ready",
        "message": None,
        "nodes": nodes,
        "links": links,
    }
