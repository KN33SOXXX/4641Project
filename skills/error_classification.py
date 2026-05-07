from __future__ import annotations

from typing import Any, Dict

from schemas import DiagnosisRecord, ParseRecord, SampleRecord
from services.vllm_client import VLLMClient
from .base import compact_dict, extract_json_object


class ErrorClassificationSkill:
    def __init__(self, llm: VLLMClient, config: Dict[str, Any]) -> None:
        self.llm = llm
        self.categories = config["agent"]["error_categories"]
        self.sampling = config["vllm"]["sampling"]["classification"]

    def run(self, sample: SampleRecord, parse: ParseRecord) -> DiagnosisRecord:
        payload = {
            "sample_id": sample.sample_id,
            "question": sample.question,
            "answer": sample.answer,
            "solution": sample.solution,
            "student_answer": sample.student_answer,
            "scratchwork_parse": parse.to_dict(),
            "allowed_categories": self.categories,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是数学作业错误诊断分类器。只输出 JSON，不要 Markdown。"
                    "pred_error_category 必须严格取 allowed_categories 中的一个。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "根据题目、标准答案、参考解法、学生答案和草稿 OCR 结果，"
                    "预测学生主要错误类型，并给出各类概率、证据区域和简短依据。\n"
                    "输出 JSON schema: {"
                    "\"pred_error_category\": string, "
                    "\"category_probs\": object, "
                    "\"evidence_regions\": array, "
                    "\"rationale\": string"
                    "}。\n"
                    f"输入:\n{compact_dict(payload)}"
                ),
            },
        ]
        content = self.llm.chat(messages, self.sampling, response_format={"type": "json_object"})
        data = extract_json_object(content)
        category = data.get("pred_error_category", "")
        if category not in self.categories:
            category = self.categories[0]
        probs = data.get("category_probs", {})
        if not isinstance(probs, dict):
            probs = {}
        return DiagnosisRecord(
            sample_id=sample.sample_id,
            pred_error_category=category,
            category_probs={str(k): float(v) for k, v in probs.items() if _is_number(v)},
            pred_error_explanation=str(data.get("rationale", "")),
            evidence_regions=list(data.get("evidence_regions", []))
            if isinstance(data.get("evidence_regions", []), list)
            else [],
            raw=data,
        )


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False
