from __future__ import annotations

from typing import Any, Dict

from schemas import ParseRecord, SampleRecord
from services.vllm_client import VLLMClient
from .base import compact_dict, extract_json_object


class StudentWorkExtractionSkill:
    def __init__(self, llm: VLLMClient, config: Dict[str, Any]) -> None:
        self.llm = llm
        self.sampling = config["vllm"]["sampling"]["classification"]

    def run(self, sample: SampleRecord, parse: ParseRecord) -> Dict[str, Any]:
        payload = {
            "sample_id": sample.sample_id,
            "question": sample.question,
            "scratchwork_ocr": parse.to_dict(),
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是学生草稿理解助手。只输出 JSON，不要 Markdown。"
                    "只能依据题目和手写草稿 OCR 结果，不得假设已知标准答案。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请从草稿中抽取学生的解题步骤和最终答案。"
                    "必须输出 JSON 对象，字段包括："
                    "student_final_answer、visible_steps、scratchwork_summary、uncertain_points、confidence。"
                    "visible_steps 和 uncertain_points 必须是字符串数组；confidence 为 0 到 1 的数字。\n"
                    f"输入:\n{compact_dict(payload, limit=6000)}"
                ),
            },
        ]
        data = extract_json_object(
            self.llm.chat(messages, self.sampling, response_format={"type": "json_object"})
        )
        return {
            "student_final_answer": str(data.get("student_final_answer", "")),
            "visible_steps": _string_list(data.get("visible_steps", [])),
            "scratchwork_summary": str(data.get("scratchwork_summary", "")),
            "uncertain_points": _string_list(data.get("uncertain_points", [])),
            "confidence": _float01(data.get("confidence", 0.0)),
            "raw": data,
        }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value:
        return [str(value)]
    return []


def _float01(value: Any) -> float:
    try:
        number = float(value)
    except Exception:
        return 0.0
    return min(1.0, max(0.0, number))
