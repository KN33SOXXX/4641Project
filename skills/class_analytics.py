from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Dict, Iterable, List

from services.vllm_client import VLLMClient
from .base import compact_dict, extract_json_object


class ClassAnalyticsSkill:
    def __init__(self, llm: VLLMClient, config: Dict[str, Any]) -> None:
        self.llm = llm
        self.sampling = config["vllm"]["sampling"]["analytics"]

    def build_graphs(self, results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        rows = list(results)
        category_counts: Counter[str] = Counter()
        bipartite_edges = []
        student_categories: Dict[str, Counter[str]] = defaultdict(Counter)

        for row in rows:
            sample = row.get("sample", {})
            diagnosis = row.get("diagnosis", {})
            sample_id = str(sample.get("sample_id", "sample"))
            student_id = str(sample.get("student_id") or sample.get("student", sample_id))
            category = str(diagnosis.get("pred_error_category", "unknown"))
            category_counts[category] += 1
            student_categories[student_id][category] += 1
            bipartite_edges.append(
                {"source": student_id, "target": category, "sample_id": sample_id, "weight": 1}
            )

        cooccurrence = Counter()
        for _, cats in student_categories.items():
            active = sorted([cat for cat, count in cats.items() if count > 0])
            for left, right in combinations(active, 2):
                cooccurrence[(left, right)] += 1

        student_similarity = []
        students = sorted(student_categories)
        for left, right in combinations(students, 2):
            lset = set(student_categories[left])
            rset = set(student_categories[right])
            union = lset | rset
            score = len(lset & rset) / len(union) if union else 0.0
            if score > 0:
                student_similarity.append({"source": left, "target": right, "weight": score})

        return {
            "sample_count": len(rows),
            "category_counts": dict(category_counts),
            "student_error_edges": bipartite_edges,
            "error_cooccurrence_edges": [
                {"source": left, "target": right, "weight": weight}
                for (left, right), weight in cooccurrence.items()
            ],
            "student_similarity_edges": student_similarity,
        }

    def summarize(self, analytics: Dict[str, Any]) -> str:
        messages = [
            {
                "role": "system",
                "content": "你是班级数学错因分析助手。输出 JSON，不要 Markdown。",
            },
            {
                "role": "user",
                "content": (
                    "根据班级错误统计生成教师端摘要，包含主要错误、共现模式和教学建议。"
                    "输出 JSON schema: {\"teacher_class_summary\": string}。\n"
                    f"输入:\n{compact_dict(analytics, limit=6000)}"
                ),
            },
        ]
        content = self.llm.chat(messages, self.sampling, response_format={"type": "json_object"})
        data = extract_json_object(content)
        return str(data.get("teacher_class_summary", ""))

    def run(self, results: Iterable[Dict[str, Any]], with_llm_summary: bool = True) -> Dict[str, Any]:
        analytics = self.build_graphs(results)
        if with_llm_summary:
            analytics["teacher_class_summary"] = self.summarize(analytics)
        return analytics
