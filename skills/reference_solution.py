from __future__ import annotations

import re
from typing import Any, Dict

from schemas import SampleRecord
from services.vllm_client import VLLMClient
from .base import compact_dict, extract_json_object


class ReferenceSolutionSkill:
    def __init__(self, llm: VLLMClient, config: Dict[str, Any]) -> None:
        self.llm = llm
        self.sampling = dict(config["vllm"]["sampling"]["explanation"])
        self.sampling["temperature"] = 0.0
        self.sampling["top_p"] = 1.0
        self.sampling["max_tokens"] = max(int(self.sampling.get("max_tokens", 1200)), 2000)

    def run(self, sample: SampleRecord) -> Dict[str, Any]:
        payload = {
            "sample_id": sample.sample_id,
            "question": sample.question,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是严谨的数学解题助手。只输出 JSON，不要 Markdown，不要输出 <think>。"
                    "只能根据题目独立求解，不要使用任何学生答案或标注答案。"
                    "先在内部核算，最终只输出一次确定答案；禁止输出“等等”“重新检查”等自我修正过程。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "/no_think\n请独立解答题目，给出参考答案和关键步骤。"
                    "必须输出 JSON 对象，字段包括："
                    "reference_answer、solution_steps、key_concepts、confidence。"
                    "solution_steps 必须是 2 到 4 条短句，每条不超过 40 个汉字；"
                    "key_concepts 最多 3 项；confidence 为 0 到 1 的数字。"
                    "不要写长推导，不要写自我对话，不要在 JSON 外输出任何文本。\n"
                    f"输入:\n{compact_dict(payload, limit=4000)}"
                ),
            },
        ]
        content = self.llm.chat(messages, self.sampling, response_format={"type": "json_object"})
        try:
            data = extract_json_object(content)
        except Exception:
            data = self._retry_compact(sample, content)
        data = _repair_reference_answer(data)
        return {
            "reference_answer": str(data.get("reference_answer", "")),
            "solution_steps": _string_list(data.get("solution_steps", [])),
            "key_concepts": _string_list(data.get("key_concepts", [])),
            "confidence": _float01(data.get("confidence", 0.0)),
            "raw": data,
        }

    def _retry_compact(self, sample: SampleRecord, previous_content: str) -> Dict[str, Any]:
        payload = {
            "question": sample.question,
            "previous_output_prefix": previous_content[:500],
        }
        messages = [
            {
                "role": "system",
                "content": "你是 JSON 修复器和数学解题助手。只输出一个合法 JSON 对象。",
            },
            {
                "role": "user",
                "content": (
                    "/no_think\n上一轮输出不是合法 JSON。请重新独立解题，并只输出紧凑 JSON："
                    "{\"reference_answer\":\"...\",\"solution_steps\":[\"...\",\"...\"],"
                    "\"key_concepts\":[\"...\"],\"confidence\":0.0}。"
                    "solution_steps 最多 3 条短句，禁止自我修正文字。\n"
                    f"输入:\n{compact_dict(payload, limit=2500)}"
                ),
            },
        ]
        retry_sampling = dict(self.sampling)
        retry_sampling["max_tokens"] = 800
        return extract_json_object(
            self.llm.chat(messages, retry_sampling, response_format={"type": "json_object"})
        )


def _repair_reference_answer(data: Dict[str, Any]) -> Dict[str, Any]:
    answer = str(data.get("reference_answer", "")).strip()
    steps = _string_list(data.get("solution_steps", []))
    joined_steps = "\n".join(steps)
    if answer and answer in joined_steps:
        return data
    candidate = ""
    for step in reversed(steps):
        matches = re.findall(r"=\s*([^=，。；;\n]+)", step)
        if matches:
            candidate = matches[-1].strip()
            break
    candidate = re.sub(r"[）)\].,，。；;\s]+$", "", candidate)
    if candidate:
        data["reference_answer"] = candidate
        data["answer_repaired_from_steps"] = True
    return data


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
