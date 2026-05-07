from __future__ import annotations

import argparse
import html
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ERROR_CATEGORIES = [
    "计算错误",
    "题目理解错误",
    "知识点错误",
    "答题技巧错误",
    "手写誊抄错误",
    "逻辑推理错误",
    "注意力与细节错误",
    "无错误",
]
ERROR_VECTOR_CATEGORIES = [category for category in ERROR_CATEGORIES if category != "无错误"]
CATEGORY_ALIASES = {
    "概念理解错误": "知识点错误",
    "审题不清": "题目理解错误",
    "手写识别相关错误": "手写誊抄错误",
    "注意力/粗心错误": "注意力与细节错误",
}
GROUP_CONFIG = {
    "primary": {"subset": "primary", "student_count": 200, "prefix": "primary_S"},
    "middle": {"subset": "middle", "student_count": 50, "prefix": "middle_S"},
}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def sample_id(row: Dict[str, Any]) -> str:
    return str(row.get("input", {}).get("sample_id") or row.get("sample", {}).get("sample_id") or "")


def subset_name(row: Dict[str, Any]) -> str:
    subset = str(row.get("input", {}).get("subset") or row.get("sample", {}).get("subset") or "")
    if subset:
        return subset
    sid = sample_id(row)
    if sid.startswith("primary-"):
        return "primary"
    if sid.startswith("middle-"):
        return "middle"
    return "unknown"


def pred_category(row: Dict[str, Any]) -> str:
    category = str(
        row.get("diagnosis", {}).get("pred_error_category")
        or row.get("final", {}).get("pred_error_category")
        or "未知"
    )
    return CATEGORY_ALIASES.get(category, category)


def round_error_count(row: Dict[str, Any]) -> int:
    return len(row.get("errors") or [])


def parse_confidence(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("parse", {}).get("parse_confidence", 0.0))
    except Exception:
        return 0.0


def stable_group_seed(seed: int, group: str) -> int:
    return seed + sum((index + 1) * ord(char) for index, char in enumerate(group))


def assign_group(rows: List[Dict[str, Any]], group: str, seed: int) -> List[Dict[str, Any]]:
    config = GROUP_CONFIG[group]
    students = [f"{config['prefix']}{index:03d}" for index in range(1, config["student_count"] + 1)]
    shuffled = sorted(rows, key=sample_id)
    random.Random(stable_group_seed(seed, group)).shuffle(shuffled)
    counters: Counter[str] = Counter()
    assigned: List[Dict[str, Any]] = []
    for index, row in enumerate(shuffled):
        student_id = students[index % len(students)]
        counters[student_id] += 1
        row_copy = json.loads(json.dumps(row, ensure_ascii=False))
        row_copy.setdefault("input", {})["student_id"] = student_id
        row_copy["input"]["group"] = group
        row_copy.setdefault("sample", {})["student_id"] = student_id
        row_copy["sample"]["group"] = group
        row_copy["assignment"] = {
            "student_id": student_id,
            "group": group,
            "assigned_index": counters[student_id],
            "assignment_seed": seed,
        }
        assigned.append(row_copy)
    return assigned


def assign_students(rows: List[Dict[str, Any]], seed: int) -> List[Dict[str, Any]]:
    by_subset: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_subset[subset_name(row)].append(row)
    assigned: List[Dict[str, Any]] = []
    assigned.extend(assign_group(by_subset["primary"], "primary", seed))
    assigned.extend(assign_group(by_subset["middle"], "middle", seed))
    assigned.sort(key=lambda row: (row["assignment"]["group"], row["assignment"]["student_id"], sample_id(row)))
    return assigned


def risk_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def build_profiles(assigned_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in assigned_rows:
        grouped[row["assignment"]["student_id"]].append(row)

    profiles: Dict[str, Dict[str, Any]] = {}
    for student_id, rows in grouped.items():
        group = rows[0]["assignment"]["group"]
        categories = Counter(pred_category(row) for row in rows)
        sample_count = len(rows)
        no_error_count = categories.get("无错误", 0)
        error_count = sample_count - no_error_count
        round_errors = sum(round_error_count(row) for row in rows)
        avg_ocr = sum(parse_confidence(row) for row in rows) / sample_count if sample_count else 0.0
        error_rate = error_count / sample_count if sample_count else 0.0
        round_error_rate = round_errors / sample_count if sample_count else 0.0
        dominant_category, dominant_count = dominant_error(categories)
        dominant_share = dominant_count / error_count if error_count else 0.0
        score = min(1.0, error_rate * 0.75 + round_error_rate * 0.15 + dominant_share * 0.10)
        profiles[student_id] = {
            "student_id": student_id,
            "group": group,
            "sample_count": sample_count,
            "error_count": error_count,
            "no_error_count": no_error_count,
            "error_rate": round(error_rate, 4),
            "round_error_count": round_errors,
            "round_error_rate": round(round_error_rate, 4),
            "avg_ocr_confidence": round(avg_ocr, 4),
            "category_counts": {category: categories.get(category, 0) for category in ERROR_CATEGORIES},
            "category_ratios": {
                category: round(categories.get(category, 0) / sample_count, 4) if sample_count else 0.0
                for category in ERROR_CATEGORIES
            },
            "dominant_error_category": dominant_category,
            "dominant_error_count": dominant_count,
            "risk_score": round(score, 4),
            "risk_level": risk_label(score),
            "representative_feedback": representative_feedback(rows),
        }
    return dict(sorted(profiles.items()))


def dominant_error(categories: Counter[str]) -> Tuple[str, int]:
    candidates = [(category, count) for category, count in categories.items() if category != "无错误"]
    if not candidates:
        return "无错误", categories.get("无错误", 0)
    return max(candidates, key=lambda item: (item[1], item[0]))


def representative_feedback(rows: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: (
            pred_category(row) == "无错误",
            -len(str(row.get("final", {}).get("teacher_summary", ""))),
            sample_id(row),
        ),
    )
    examples: List[Dict[str, Any]] = []
    for row in ranked[:limit]:
        final = row.get("final", {})
        examples.append(
            {
                "sample_id": sample_id(row),
                "category": pred_category(row),
                "student_feedback": clip(final.get("student_feedback", ""), 260),
                "next_step_advice": clip(final.get("next_step_advice", ""), 220),
                "teacher_summary": clip(final.get("teacher_summary", ""), 320),
            }
        )
    return examples


def cosine(left: List[float], right: List[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    lnorm = math.sqrt(sum(a * a for a in left))
    rnorm = math.sqrt(sum(b * b for b in right))
    if not lnorm or not rnorm:
        return 0.0
    return dot / (lnorm * rnorm)


def build_similarity_graph(
    profiles: Dict[str, Dict[str, Any]],
    max_neighbors: int,
    min_similarity: float,
) -> Dict[str, Any]:
    ids = sorted(profiles)
    vectors = {
        student_id: [profiles[student_id]["category_counts"].get(category, 0) for category in ERROR_VECTOR_CATEGORIES]
        for student_id in ids
    }
    neighbors: Dict[str, List[Tuple[str, float]]] = {student_id: [] for student_id in ids}
    for left_index, left_id in enumerate(ids):
        for right_id in ids[left_index + 1 :]:
            score = cosine(vectors[left_id], vectors[right_id])
            if score >= min_similarity:
                neighbors[left_id].append((right_id, score))
                neighbors[right_id].append((left_id, score))

    edge_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for student_id, pairs in neighbors.items():
        for other_id, score in sorted(pairs, key=lambda item: item[1], reverse=True)[:max_neighbors]:
            left, right = sorted([student_id, other_id])
            edge_map[(left, right)] = {
                "source": left,
                "target": right,
                "weight": round(score, 4),
                "same_group": profiles[left]["group"] == profiles[right]["group"],
                "shared_error_categories": shared_categories(profiles[left], profiles[right]),
            }
    nodes = [
        {
            "id": student_id,
            "group": profile["group"],
            "sample_count": profile["sample_count"],
            "error_count": profile["error_count"],
            "error_rate": profile["error_rate"],
            "dominant_error_category": profile["dominant_error_category"],
            "risk_score": profile["risk_score"],
            "risk_level": profile["risk_level"],
        }
        for student_id, profile in profiles.items()
    ]
    edges = sorted(edge_map.values(), key=lambda edge: (-edge["weight"], edge["source"], edge["target"]))
    graph = {
        "graph_type": "student_error_similarity",
        "vector_categories": ERROR_VECTOR_CATEGORIES,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
    enrich_graph(graph, profiles)
    return graph


def shared_categories(left: Dict[str, Any], right: Dict[str, Any]) -> List[str]:
    shared = []
    for category in ERROR_VECTOR_CATEGORIES:
        if left["category_counts"].get(category, 0) and right["category_counts"].get(category, 0):
            shared.append(category)
    return shared[:4]


def enrich_graph(graph: Dict[str, Any], profiles: Dict[str, Dict[str, Any]]) -> None:
    nodes = graph["nodes"]
    edges = graph["edges"]
    node_by_id = {node["id"]: node for node in nodes}
    degree: Counter[str] = Counter()
    weighted_degree: Counter[str] = Counter()
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        weight = float(edge.get("weight", 0.0))
        degree[source] += 1
        degree[target] += 1
        weighted_degree[source] += weight
        weighted_degree[target] += weight

    communities = detect_communities([node["id"] for node in nodes], edges)
    for node in nodes:
        node_id = node["id"]
        node["degree"] = int(degree[node_id])
        node["weighted_degree"] = round(float(weighted_degree[node_id]), 4)
        node["community_id"] = communities.get(node_id, "C00")
    for edge in edges:
        edge["same_community"] = communities.get(edge["source"]) == communities.get(edge["target"])

    community_summary = summarize_communities(nodes, profiles)
    component_count, largest_component = connected_component_stats([node["id"] for node in nodes], edges)
    graph["communities"] = community_summary
    graph["analysis"] = {
        "community_count": len(community_summary),
        "component_count": component_count,
        "largest_component_size": largest_component,
        "density": round((2 * len(edges)) / (len(nodes) * (len(nodes) - 1)), 4) if len(nodes) > 1 else 0.0,
        "avg_similarity": round(sum(float(edge.get("weight", 0.0)) for edge in edges) / len(edges), 4)
        if edges
        else 0.0,
        "high_risk_students": sum(1 for node in nodes if node.get("risk_level") == "high"),
        "top_hubs": [
            {
                "student_id": node["id"],
                "weighted_degree": node["weighted_degree"],
                "degree": node["degree"],
                "community_id": node["community_id"],
                "dominant_error_category": node["dominant_error_category"],
                "risk_level": node["risk_level"],
            }
            for node in sorted(nodes, key=lambda item: item.get("weighted_degree", 0.0), reverse=True)[:10]
        ],
    }


def detect_communities(node_ids: List[str], edges: List[Dict[str, Any]], iterations: int = 24) -> Dict[str, str]:
    adjacency: Dict[str, List[Tuple[str, float]]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        weight = float(edge.get("weight", 0.0))
        adjacency.setdefault(source, []).append((target, weight))
        adjacency.setdefault(target, []).append((source, weight))
    labels = {node_id: node_id for node_id in node_ids}
    for _ in range(iterations):
        changed = False
        for node_id in sorted(node_ids):
            scores: Counter[str] = Counter()
            for other_id, weight in adjacency.get(node_id, []):
                scores[labels[other_id]] += weight
            if not scores:
                continue
            best_label, _ = max(scores.items(), key=lambda item: (item[1], -len(item[0]), item[0]))
            if labels[node_id] != best_label:
                labels[node_id] = best_label
                changed = True
        if not changed:
            break
    grouped: Dict[str, List[str]] = defaultdict(list)
    for node_id, label in labels.items():
        grouped[label].append(node_id)
    ordered_labels = sorted(grouped, key=lambda label: (-len(grouped[label]), min(grouped[label])))
    normalized = {label: f"C{index + 1:02d}" for index, label in enumerate(ordered_labels)}
    return {node_id: normalized[label] for node_id, label in labels.items()}


def summarize_communities(nodes: List[Dict[str, Any]], profiles: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        grouped[node["community_id"]].append(node)
    summaries: List[Dict[str, Any]] = []
    for community_id, community_nodes in grouped.items():
        category_counts: Counter[str] = Counter()
        risk_counts: Counter[str] = Counter()
        for node in community_nodes:
            profile = profiles[node["id"]]
            category_counts.update(profile["category_counts"])
            risk_counts[profile["risk_level"]] += 1
        dominant, count = dominant_error(category_counts)
        avg_error_rate = sum(float(node["error_rate"]) for node in community_nodes) / len(community_nodes)
        avg_risk = sum(float(node["risk_score"]) for node in community_nodes) / len(community_nodes)
        hubs = sorted(community_nodes, key=lambda node: node.get("weighted_degree", 0.0), reverse=True)[:5]
        summaries.append(
            {
                "community_id": community_id,
                "size": len(community_nodes),
                "dominant_error_category": dominant,
                "dominant_error_count": count,
                "avg_error_rate": round(avg_error_rate, 4),
                "avg_risk_score": round(avg_risk, 4),
                "risk_counts": dict(risk_counts),
                "category_counts": {category: category_counts.get(category, 0) for category in ERROR_CATEGORIES},
                "hub_students": [
                    {
                        "student_id": node["id"],
                        "weighted_degree": node.get("weighted_degree", 0.0),
                        "dominant_error_category": node["dominant_error_category"],
                        "risk_level": node["risk_level"],
                    }
                    for node in hubs
                ],
            }
        )
    return sorted(summaries, key=lambda item: (-item["size"], item["community_id"]))


def connected_component_stats(node_ids: List[str], edges: List[Dict[str, Any]]) -> Tuple[int, int]:
    adjacency: Dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in edges:
        adjacency.setdefault(edge["source"], set()).add(edge["target"])
        adjacency.setdefault(edge["target"], set()).add(edge["source"])
    seen: set[str] = set()
    sizes: List[int] = []
    for node_id in node_ids:
        if node_id in seen:
            continue
        stack = [node_id]
        seen.add(node_id)
        size = 0
        while stack:
            current = stack.pop()
            size += 1
            for nxt in adjacency.get(current, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        sizes.append(size)
    return len(sizes), max(sizes) if sizes else 0


def build_group_summary(
    assigned_rows: List[Dict[str, Any]],
    profiles: Dict[str, Dict[str, Any]],
    graphs: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "total_samples": len(assigned_rows),
        "total_students": len(profiles),
        "groups": {},
        "round_error_distribution": Counter(),
    }
    for row in assigned_rows:
        summary["round_error_distribution"][str(round_error_count(row))] += 1

    for group in ("primary", "middle"):
        group_rows = [row for row in assigned_rows if row["assignment"]["group"] == group]
        group_profiles = [profile for profile in profiles.values() if profile["group"] == group]
        category_counts = Counter(pred_category(row) for row in group_rows)
        risk_counts = Counter(profile["risk_level"] for profile in group_profiles)
        avg_error_rate = (
            sum(profile["error_rate"] for profile in group_profiles) / len(group_profiles)
            if group_profiles
            else 0.0
        )
        top_risk = sorted(group_profiles, key=lambda profile: profile["risk_score"], reverse=True)[:15]
        summary["groups"][group] = {
            "sample_count": len(group_rows),
            "student_count": len(group_profiles),
            "avg_samples_per_student": round(len(group_rows) / len(group_profiles), 2) if group_profiles else 0.0,
            "avg_error_rate": round(avg_error_rate, 4),
            "category_counts": {category: category_counts.get(category, 0) for category in ERROR_CATEGORIES},
            "risk_counts": dict(risk_counts),
            "graph_analysis": (graphs or {}).get(group, {}).get("analysis", {}),
            "top_risk_students": [
                {
                    "student_id": profile["student_id"],
                    "risk_score": profile["risk_score"],
                    "risk_level": profile["risk_level"],
                    "dominant_error_category": profile["dominant_error_category"],
                    "error_rate": profile["error_rate"],
                    "sample_count": profile["sample_count"],
                }
                for profile in top_risk
            ],
        }
    summary["round_error_distribution"] = dict(summary["round_error_distribution"])
    return summary


def write_report(
    path: Path,
    summary: Dict[str, Any],
    profiles: Dict[str, Dict[str, Any]],
    graphs: Dict[str, Dict[str, Any]],
) -> None:
    top_risk = sorted(profiles.values(), key=lambda profile: profile["risk_score"], reverse=True)[:30]
    examples = []
    for profile in top_risk[:12]:
        for feedback in profile["representative_feedback"][:1]:
            examples.append({"student_id": profile["student_id"], "group": profile["group"], **feedback})

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>ScratchMath Student Social Report</title>
<style>
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2937; background: #f8fafc; }}
header {{ padding: 28px 36px; background: #102033; color: white; }}
h1 {{ margin: 0 0 8px; font-size: 28px; }}
h2 {{ margin: 32px 0 14px; font-size: 20px; }}
main {{ padding: 24px 36px 48px; }}
.cards {{ display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 14px; }}
.card {{ background: white; border: 1px solid #d7dde6; border-radius: 8px; padding: 16px; }}
.metric {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #d7dde6; }}
th, td {{ padding: 9px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; font-size: 13px; }}
th {{ background: #eef2f7; font-weight: 700; }}
.panel {{ background: white; border: 1px solid #d7dde6; border-radius: 8px; padding: 16px; overflow: auto; }}
.badge {{ display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 12px; background: #e5e7eb; }}
.high {{ background: #fee2e2; color: #991b1b; }}
.medium {{ background: #fef3c7; color: #92400e; }}
.low {{ background: #dcfce7; color: #166534; }}
svg text {{ font-family: inherit; }}
.muted {{ color: #64748b; }}
.graph-grid {{ display: grid; grid-template-columns: 1fr; gap: 18px; }}
.community {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
.edge-flow {{ stroke-dasharray: 7 10; animation: flow 8s linear infinite; }}
.community-ring {{ stroke-dasharray: 5 7; animation: flow 18s linear infinite; }}
@keyframes flow {{ to {{ stroke-dashoffset: -120; }} }}
@media (max-width: 900px) {{ .cards, .grid, .community {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header>
<h1>ScratchMath 学生错误 Social 图报告</h1>
<div>primary 200 名虚拟学生，middle 50 名虚拟学生；两组独立建图、社区发现与错误画像分析。</div>
</header>
<main>
<section class="cards">
{cards_html(summary, graphs)}
</section>
<section class="grid">
<div class="panel">
<h2>组别错因分布</h2>
{category_chart_svg(summary)}
</div>
<div class="panel">
<h2>组别概览</h2>
{group_table_html(summary)}
</div>
</section>
<section class="panel">
<h2>图分析概览</h2>
{graph_analysis_table(graphs)}
</section>
<section class="graph-grid">
<div class="panel">
<h2>Primary 学生错误相似动态图</h2>
<p class="muted">节点为 primary 学生，边表示错误类别分布相似；外圈为社区，节点脉冲和边流动用于突出网络结构。</p>
{network_svg(graphs["primary"], "primary")}
</div>
<div class="panel">
<h2>Middle 学生错误相似动态图</h2>
<p class="muted">节点为 middle 学生，边表示错误类别分布相似；社区由加权标签传播自动检测。</p>
{network_svg(graphs["middle"], "middle")}
</div>
</section>
<section class="community">
<div class="panel">
<h2>Primary 社区画像</h2>
{community_table(graphs["primary"])}
</div>
<div class="panel">
<h2>Middle 社区画像</h2>
{community_table(graphs["middle"])}
</div>
</section>
<section class="grid">
<div class="panel">
<h2>高风险学生</h2>
{top_risk_table(top_risk)}
</div>
<div class="panel">
<h2>代表性 Feedback</h2>
{feedback_table(examples)}
</div>
</section>
</main>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def cards_html(summary: Dict[str, Any], graphs: Dict[str, Dict[str, Any]]) -> str:
    total_edges = sum(graph["edge_count"] for graph in graphs.values())
    total_communities = sum(graph["analysis"]["community_count"] for graph in graphs.values())
    cards = [
        ("样本数", summary["total_samples"]),
        ("学生数", summary["total_students"]),
        ("独立图数量", len(graphs)),
        ("社区数量", total_communities),
        ("Social 图边", total_edges),
    ]
    return "\n".join(
        f'<div class="card"><div class="muted">{escape(label)}</div><div class="metric">{value}</div></div>'
        for label, value in cards
    )


def group_table_html(summary: Dict[str, Any]) -> str:
    rows = []
    for group, payload in summary["groups"].items():
        rows.append(
            "<tr>"
            f"<td>{escape(group)}</td>"
            f"<td>{payload['student_count']}</td>"
            f"<td>{payload['sample_count']}</td>"
            f"<td>{payload['avg_samples_per_student']}</td>"
            f"<td>{payload['avg_error_rate']:.2%}</td>"
            f"<td>{escape(str(payload['risk_counts']))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>组别</th><th>学生</th><th>样本</th><th>人均题量</th><th>平均错误率</th><th>风险分布</th></tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def category_chart_svg(summary: Dict[str, Any]) -> str:
    width, height = 720, 320
    left, top = 120, 28
    bar_h, gap = 12, 9
    max_value = max(
        max(group["category_counts"].values()) for group in summary["groups"].values()
    )
    scale = (width - left - 60) / max_value if max_value else 1
    colors = {"primary": "#2563eb", "middle": "#16a34a"}
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    y = top
    for category in ERROR_CATEGORIES:
        parts.append(f'<text x="8" y="{y + 12}" font-size="12">{escape(category)}</text>')
        for group in ("primary", "middle"):
            value = summary["groups"][group]["category_counts"].get(category, 0)
            w = value * scale
            parts.append(
                f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{colors[group]}" opacity="{0.80 if group == "primary" else 0.55}"></rect>'
            )
            parts.append(f'<text x="{left + w + 5:.1f}" y="{y + 10}" font-size="11">{value}</text>')
            y += bar_h + 2
        y += gap
    parts.append(f'<text x="{left}" y="{height - 8}" font-size="12" fill="{colors["primary"]}">primary</text>')
    parts.append(f'<text x="{left + 90}" y="{height - 8}" font-size="12" fill="{colors["middle"]}">middle</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def network_svg(graph: Dict[str, Any], title: str) -> str:
    width, height = 1180, 700
    nodes = sorted(graph["nodes"], key=lambda node: node["id"])
    positions, community_centers = node_positions(nodes, width, height)
    edge_limit = 620 if title == "primary" else 260
    top_edges = sorted(graph["edges"], key=lambda edge: edge["weight"], reverse=True)[:edge_limit]
    community_sizes = Counter(node.get("community_id", "C00") for node in nodes)
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    parts.append('<rect width="100%" height="100%" fill="#f8fafc"></rect>')
    for community_id, (cx, cy) in community_centers.items():
        size = community_sizes.get(community_id, 1)
        radius = 34 + min(112, size * 3.2)
        parts.append(
            f'<circle class="community-ring" cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" fill="none" stroke="#94a3b8" stroke-width="1" opacity="0.32"></circle>'
        )
        parts.append(f'<text x="{cx - 18:.1f}" y="{cy - radius - 8:.1f}" font-size="11" fill="#475569">{escape(community_id)} ({size})</text>')
    for edge in top_edges:
        source = positions.get(edge["source"])
        target = positions.get(edge["target"])
        if not source or not target:
            continue
        opacity = 0.08 + edge["weight"] * 0.28
        parts.append(
            f'<line class="edge-flow" x1="{source[0]:.1f}" y1="{source[1]:.1f}" x2="{target[0]:.1f}" y2="{target[1]:.1f}" stroke="#64748b" stroke-width="{0.4 + edge["weight"] * 2.0:.2f}" opacity="{opacity:.2f}"><title>{escape(edge["source"])} ↔ {escape(edge["target"])} similarity={edge["weight"]}</title></line>'
        )
    for node in nodes:
        x, y = positions[node["id"]]
        radius = 3.5 + min(7.0, node["error_count"] * 0.8)
        fill = "#60a5fa" if node["group"] == "primary" else "#4ade80"
        stroke = {"high": "#dc2626", "medium": "#f59e0b", "low": "#16a34a"}.get(node["risk_level"], "#475569")
        title = escape(
            f"{node['id']} | {node['group']} | {node['community_id']} | {node['dominant_error_category']} | error_rate={node['error_rate']} | weighted_degree={node.get('weighted_degree', 0)}"
        )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.7"><title>{title}</title><animate attributeName="r" values="{radius:.1f};{radius + 1.8:.1f};{radius:.1f}" dur="{3.2 + (len(node["id"]) % 5) * 0.35:.2f}s" repeatCount="indefinite"/></circle>'
        )
        if node["risk_level"] == "high":
            parts.append(f'<text x="{x + 7:.1f}" y="{y + 4:.1f}" font-size="10">{escape(node["id"])}</text>')
    parts.append(f'<text x="28" y="34" font-size="13" fill="#334155">{escape(title)} graph: {graph["node_count"]} nodes, {graph["edge_count"]} edges, {graph["analysis"]["community_count"]} communities</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def node_positions(nodes: List[Dict[str, Any]], width: int, height: int) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, Tuple[float, float]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        grouped[node.get("community_id", "C00")].append(node)
    positions: Dict[str, Tuple[float, float]] = {}
    centers: Dict[str, Tuple[float, float]] = {}
    community_ids = sorted(grouped, key=lambda cid: (-len(grouped[cid]), cid))
    center_radius = min(width, height) * 0.31
    for cindex, community_id in enumerate(community_ids):
        angle = 2 * math.pi * cindex / max(1, len(community_ids))
        cx = width / 2 + math.cos(angle) * center_radius
        cy = height / 2 + math.sin(angle) * center_radius * 0.72
        centers[community_id] = (cx, cy)
        group_nodes = grouped[community_id]
        ordered = sorted(group_nodes, key=lambda node: (-node["risk_score"], -node.get("weighted_degree", 0), node["id"]))
        local_radius = 18 + min(104, len(ordered) * 3.4)
        for index, node in enumerate(ordered):
            angle = 2 * math.pi * index / max(1, len(ordered))
            ring = local_radius * (0.58 + 0.42 * ((index % 4) / 3))
            positions[node["id"]] = (cx + math.cos(angle) * ring, cy + math.sin(angle) * ring)
    return positions, centers


def graph_analysis_table(graphs: Dict[str, Dict[str, Any]]) -> str:
    rows = []
    for group, graph in graphs.items():
        analysis = graph["analysis"]
        rows.append(
            "<tr>"
            f"<td>{escape(group)}</td>"
            f"<td>{graph['node_count']}</td>"
            f"<td>{graph['edge_count']}</td>"
            f"<td>{analysis['community_count']}</td>"
            f"<td>{analysis['component_count']}</td>"
            f"<td>{analysis['density']:.4f}</td>"
            f"<td>{analysis['avg_similarity']:.4f}</td>"
            f"<td>{analysis['high_risk_students']}</td>"
            f"<td>{escape(', '.join(item['student_id'] for item in analysis['top_hubs'][:3]))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>图</th><th>节点</th><th>边</th><th>社区</th><th>连通分量</th><th>密度</th><th>平均相似度</th><th>高风险节点</th><th>Top hubs</th></tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def community_table(graph: Dict[str, Any]) -> str:
    rows = []
    for community in graph.get("communities", []):
        hubs = ", ".join(item["student_id"] for item in community.get("hub_students", [])[:3])
        rows.append(
            "<tr>"
            f"<td>{escape(community['community_id'])}</td>"
            f"<td>{community['size']}</td>"
            f"<td>{escape(community['dominant_error_category'])}</td>"
            f"<td>{community['avg_error_rate']:.2%}</td>"
            f"<td>{community['avg_risk_score']:.2f}</td>"
            f"<td>{escape(str(community['risk_counts']))}</td>"
            f"<td>{escape(hubs)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>社区</th><th>规模</th><th>主错因</th><th>平均错误率</th><th>平均风险</th><th>风险分布</th><th>Hub 学生</th></tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def top_risk_table(profiles: List[Dict[str, Any]]) -> str:
    rows = []
    for profile in profiles:
        rows.append(
            "<tr>"
            f"<td>{escape(profile['student_id'])}</td>"
            f"<td>{escape(profile['group'])}</td>"
            f"<td><span class=\"badge {profile['risk_level']}\">{profile['risk_level']}</span></td>"
            f"<td>{profile['risk_score']:.2f}</td>"
            f"<td>{profile['error_rate']:.2%}</td>"
            f"<td>{escape(profile['dominant_error_category'])}</td>"
            f"<td>{profile['sample_count']}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>学生</th><th>组别</th><th>风险</th><th>分数</th><th>错误率</th><th>主要错因</th><th>题量</th></tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def feedback_table(examples: List[Dict[str, Any]]) -> str:
    rows = []
    for item in examples:
        rows.append(
            "<tr>"
            f"<td>{escape(item['student_id'])}</td>"
            f"<td>{escape(item['category'])}</td>"
            f"<td>{escape(item['teacher_summary'])}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>学生</th><th>错因</th><th>教师摘要</th></tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>"


def clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build virtual-student social graph report from ScratchMath agent results")
    parser.add_argument("--input", default="/data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_10005.jsonl")
    parser.add_argument("--out-dir", default="/data2/social_workspace/outputs/social_report")
    parser.add_argument("--seed", type=int, default=20260430)
    parser.add_argument("--max-neighbors", type=int, default=5)
    parser.add_argument("--min-similarity", type=float, default=0.2)
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out_dir)
    rows = read_jsonl(input_path)
    assigned = assign_students(rows, seed=args.seed)
    profiles = build_profiles(assigned)
    profile_groups = {
        group: {student_id: profile for student_id, profile in profiles.items() if profile["group"] == group}
        for group in ("primary", "middle")
    }
    graphs = {
        group: build_similarity_graph(group_profiles, args.max_neighbors, args.min_similarity)
        for group, group_profiles in profile_groups.items()
    }
    summary = build_group_summary(assigned, profiles, graphs)
    summary["source"] = str(input_path)
    summary["assignment_seed"] = args.seed
    summary["outputs"] = {
        "assigned_results_jsonl": str(out_dir / "assigned_results.jsonl"),
        "student_profiles_json": str(out_dir / "student_profiles.json"),
        "student_similarity_graph_json": str(out_dir / "student_similarity_graph.json"),
        "primary_student_similarity_graph_json": str(out_dir / "primary_student_similarity_graph.json"),
        "middle_student_similarity_graph_json": str(out_dir / "middle_student_similarity_graph.json"),
        "group_summary_json": str(out_dir / "group_summary.json"),
        "html_report": str(out_dir / "report.html"),
    }

    write_jsonl(out_dir / "assigned_results.jsonl", assigned)
    write_json(out_dir / "student_profiles.json", profiles)
    write_json(out_dir / "primary_student_similarity_graph.json", graphs["primary"])
    write_json(out_dir / "middle_student_similarity_graph.json", graphs["middle"])
    write_json(out_dir / "student_similarity_graph.json", {"graph_type": "independent_group_graphs", "graphs": graphs})
    write_json(out_dir / "group_summary.json", summary)
    write_report(out_dir / "report.html", summary, profiles, graphs)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
