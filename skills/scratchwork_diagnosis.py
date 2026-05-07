from __future__ import annotations

from typing import Any, Dict

from schemas import DiagnosisRecord, ParseRecord, SampleRecord
from services.vllm_client import VLLMClient
from .base import compact_dict, extract_json_object


class ScratchworkDiagnosisSkill:
    def __init__(self, llm: VLLMClient, config: Dict[str, Any]) -> None:
        self.llm = llm
        self.categories = config["agent"]["error_categories"]
        self.sampling = config["vllm"]["sampling"]["classification"]

    def run(
        self,
        sample: SampleRecord,
        parse: ParseRecord,
        student_work: Dict[str, Any],
        reference_solution: Dict[str, Any],
    ) -> DiagnosisRecord:
        payload = {
            "sample_id": sample.sample_id,
            "question": sample.question,
            "scratchwork_ocr": parse.to_dict(),
            "student_work_extraction": student_work,
            "reference_solution": reference_solution,
            "allowed_categories": self.categories,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是数学作业错因诊断助手。只输出 JSON，不要 Markdown。"
                    "只能使用题目、草稿 OCR、学生作答抽取结果和你独立求得的参考解。"
                    "pred_error_category 必须严格取 allowed_categories 中的一个。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请比较学生草稿与参考解，判断主要错因，给出证据和修正提示。"
                    "必须输出 JSON 对象，字段包括："
                    "pred_error_category、category_probs、rationale、evidence_regions、evidence_spans、repair_hint。"
                    "category_probs 的 key 必须来自 allowed_categories，value 为 0 到 1 的数字。\n"
                    f"输入:\n{compact_dict(payload, limit=8000)}"
                ),
            },
        ]
        data = extract_json_object(
            self.llm.chat(messages, self.sampling, response_format={"type": "json_object"})
        )
        category = str(data.get("pred_error_category", ""))
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
            evidence_regions=_string_list(data.get("evidence_regions", [])),
            evidence_spans=_string_list(data.get("evidence_spans", [])),
            repair_hint=str(data.get("repair_hint", "")),
            raw=data,
        )


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value:
        return [str(value)]
    return []


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False
