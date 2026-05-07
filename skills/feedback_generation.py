from __future__ import annotations

from typing import Any, Dict

from schemas import DiagnosisRecord, FeedbackRecord, ParseRecord, SampleRecord
from services.vllm_client import VLLMClient
from .base import compact_dict, extract_json_object


class FeedbackGenerationSkill:
    def __init__(self, llm: VLLMClient, config: Dict[str, Any]) -> None:
        self.llm = llm
        self.sections = config["agent"]["feedback_sections"]
        self.sampling = config["vllm"]["sampling"]["explanation"]

    def build_analysis_graph(
        self,
        sample: SampleRecord,
        parse: ParseRecord,
        diagnosis: DiagnosisRecord,
        student_work: Dict[str, Any] | None = None,
        reference_solution: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        student_work = student_work or {}
        reference_solution = reference_solution or {}
        nodes: list[Dict[str, Any]] = []
        edges: list[Dict[str, Any]] = []

        def add_node(node_id: str, node_type: str, **attrs: Any) -> None:
            payload = {
                "id": node_id,
                "type": node_type,
                **{key: value for key, value in attrs.items() if value not in ("", None, [], {})},
            }
            nodes.append(payload)

        def add_edge(source: str, target: str, edge_type: str, **attrs: Any) -> None:
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "type": edge_type,
                    **{key: value for key, value in attrs.items() if value not in ("", None, [], {})},
                }
            )

        add_node("question", "question", text=_clip(sample.question, 800), subset=sample.subset)
        add_node(
            "ocr",
            "ocr_parse",
            confidence=parse.parse_confidence,
            ocr_lines=[_clip(line, 160) for line in parse.ocr_lines[:12]],
            formula_candidates=[_clip(line, 160) for line in parse.formula_candidates[:8]],
            error=parse.error,
        )
        add_edge("question", "ocr", "has_scratchwork_parse")

        student_answer = _clip(student_work.get("student_final_answer", ""), 240)
        add_node(
            "student_answer",
            "student_answer",
            text=student_answer,
            confidence=student_work.get("confidence"),
            summary=_clip(student_work.get("scratchwork_summary", ""), 500),
        )
        add_edge("ocr", "student_answer", "extracts")

        for index, step in enumerate(_string_list(student_work.get("visible_steps", []))[:8]):
            node_id = f"student_step_{index}"
            add_node(node_id, "student_step", text=_clip(step, 240), order=index + 1)
            add_edge("ocr", node_id, "extracts_step")
            add_edge(node_id, "student_answer", "supports_answer")

        for index, point in enumerate(_string_list(student_work.get("uncertain_points", []))[:5]):
            node_id = f"uncertain_{index}"
            add_node(node_id, "uncertainty", text=_clip(point, 240), order=index + 1)
            add_edge("ocr", node_id, "has_uncertainty")

        reference_answer = _clip(reference_solution.get("reference_answer", ""), 240)
        add_node(
            "reference_answer",
            "reference_answer",
            text=reference_answer,
            confidence=reference_solution.get("confidence"),
        )
        add_edge("question", "reference_answer", "solved_by")
        add_edge("student_answer", "reference_answer", "compared_with")

        for index, step in enumerate(_string_list(reference_solution.get("solution_steps", []))[:8]):
            node_id = f"reference_step_{index}"
            add_node(node_id, "reference_step", text=_clip(step, 240), order=index + 1)
            add_edge("question", node_id, "has_reference_step")
            add_edge(node_id, "reference_answer", "supports_answer")

        for index, concept in enumerate(_string_list(reference_solution.get("key_concepts", []))[:6]):
            node_id = f"concept_{index}"
            add_node(node_id, "key_concept", text=_clip(concept, 120), order=index + 1)
            add_edge("question", node_id, "requires_concept")

        add_node(
            "diagnosis",
            "diagnosis",
            category=diagnosis.pred_error_category,
            explanation=_clip(diagnosis.pred_error_explanation, 800),
            repair_hint=_clip(diagnosis.repair_hint, 500),
            category_probs=_top_probs(diagnosis.category_probs),
        )
        add_edge("diagnosis", "student_answer", "explains")
        add_edge("diagnosis", "reference_answer", "uses_reference")

        for index, span in enumerate(_string_list(diagnosis.evidence_spans)[:8]):
            node_id = f"evidence_{index}"
            add_node(node_id, "evidence", text=_clip(span, 240), order=index + 1)
            add_edge("diagnosis", node_id, "supported_by")

        graph_summary = {
            "sample_id": sample.sample_id,
            "pred_error_category": diagnosis.pred_error_category,
            "student_answer": student_answer,
            "reference_answer": reference_answer,
            "main_gap": _main_gap(student_answer, reference_answer, diagnosis),
            "repair_hint": diagnosis.repair_hint,
            "confidence": {
                "ocr": parse.parse_confidence,
                "student_work": student_work.get("confidence", 0.0),
                "reference_solution": reference_solution.get("confidence", 0.0),
            },
            "low_confidence_warning": _has_low_confidence(parse, student_work, reference_solution),
        }
        return {
            "graph_type": "single_sample_feedback_analysis",
            "nodes": nodes,
            "edges": edges,
            "graph_summary": graph_summary,
        }

    def run(
        self,
        sample: SampleRecord,
        parse: ParseRecord,
        diagnosis: DiagnosisRecord,
        student_work: Dict[str, Any] | None = None,
        reference_solution: Dict[str, Any] | None = None,
        analysis_graph: Dict[str, Any] | None = None,
    ) -> FeedbackRecord:
        analysis_graph = analysis_graph or self.build_analysis_graph(
            sample, parse, diagnosis, student_work, reference_solution
        )
        payload = {"analysis_graph": analysis_graph, "required_sections": self.sections}
        messages = [
            {
                "role": "system",
                "content": (
                    "你是面向学生和教师的作业反馈助手。只输出 JSON，不要 Markdown。"
                    "你必须基于输入的诊断分析图进行推理，不要绕过图直接复述原始 OCR。"
                    "学生反馈要温和、具体、可操作；教师摘要要说明图中证据和置信度风险。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "根据 analysis_graph 生成三段式学生反馈、下一步练习建议和教师摘要。"
                    "必须解释图中的主要差距、证据路径和修正方向。"
                    "如果 graph_summary.low_confidence_warning 为 true，必须在 teacher_summary 中提示人工复核。"
                    "必须输出一个 JSON 对象，包含 student_feedback、next_step_advice、teacher_summary、graph_reasoning_summary 四个字段。"
                    "每个字段都要写完整中文句子，不要输出字段类型名、占位符或示例值；"
                    "禁止把字段值写成 string、null、N/A 或空字符串。\n"
                    f"输入:\n{compact_dict(payload, limit=8000)}"
                ),
            },
        ]
        content = self.llm.chat(messages, self.sampling, response_format={"type": "json_object"})
        data = extract_json_object(content)
        if any(_is_placeholder(data.get(key)) for key in ("student_feedback", "next_step_advice", "teacher_summary")):
            data = _fallback_feedback(diagnosis, analysis_graph)
        data["analysis_graph"] = analysis_graph
        return FeedbackRecord(
            sample_id=sample.sample_id,
            student_feedback=str(data.get("student_feedback", "")),
            next_step_advice=str(data.get("next_step_advice", "")),
            teacher_summary=str(data.get("teacher_summary", "")),
            raw=data,
        )


def _is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in {"", "string", "null", "n/a", "none", "示例", "example"}


def _fallback_feedback(diagnosis: DiagnosisRecord, analysis_graph: Dict[str, Any] | None = None) -> Dict[str, str]:
    summary = (analysis_graph or {}).get("graph_summary", {})
    if diagnosis.pred_error_category == "无错误":
        return {
            "student_feedback": "这道题的计算过程和最终答案都正确，请继续保持先写关键步骤、再核对结果的习惯。",
            "next_step_advice": "下一步可以练习同类型题，并在每题完成后检查括号内运算和最终答案是否一致。",
            "teacher_summary": "学生本题作答正确，草稿中的关键算式与参考答案一致。",
            "graph_reasoning_summary": "分析图显示学生答案与参考答案一致，未形成需要修正的主要差距。",
        }
    explanation = diagnosis.pred_error_explanation or f"本题主要问题属于{diagnosis.pred_error_category}。"
    hint = diagnosis.repair_hint or "请回到题目条件，按参考解法逐步检查每一步。"
    graph_gap = summary.get("main_gap") or explanation
    return {
        "student_feedback": f"{graph_gap} 建议先定位出错步骤，再重新计算并核对答案。",
        "next_step_advice": hint,
        "teacher_summary": f"预测错误类型：{diagnosis.pred_error_category}；建议关注学生是否能解释修正步骤。",
        "graph_reasoning_summary": f"分析图将学生答案、参考答案和诊断证据连接起来，主要差距为：{graph_gap}",
    }


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def _top_probs(probs: Dict[str, float]) -> Dict[str, float]:
    items = sorted(probs.items(), key=lambda item: float(item[1]), reverse=True)
    return {str(key): float(value) for key, value in items[:5]}


def _main_gap(student_answer: str, reference_answer: str, diagnosis: DiagnosisRecord) -> str:
    if diagnosis.pred_error_category == "无错误":
        return "分析图未发现学生答案与参考答案之间的主要差距。"
    if student_answer and reference_answer and student_answer != reference_answer:
        return f"学生答案“{student_answer}”与参考答案“{reference_answer}”不一致。"
    if diagnosis.pred_error_explanation:
        return _clip(diagnosis.pred_error_explanation, 300)
    return f"主要错因被诊断为“{diagnosis.pred_error_category}”。"


def _has_low_confidence(
    parse: ParseRecord,
    student_work: Dict[str, Any],
    reference_solution: Dict[str, Any],
) -> bool:
    try:
        ocr_confidence = float(parse.parse_confidence)
    except Exception:
        ocr_confidence = 0.0
    try:
        student_confidence = float(student_work.get("confidence", 0.0))
    except Exception:
        student_confidence = 0.0
    try:
        reference_confidence = float(reference_solution.get("confidence", 0.0))
    except Exception:
        reference_confidence = 0.0
    return ocr_confidence < 0.45 or student_confidence < 0.45 or reference_confidence < 0.5
