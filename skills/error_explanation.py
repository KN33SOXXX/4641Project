from __future__ import annotations

from typing import Any, Dict

from schemas import DiagnosisRecord, ParseRecord, SampleRecord
from services.vllm_client import VLLMClient
from .base import compact_dict, extract_json_object


class ErrorExplanationSkill:
    def __init__(self, llm: VLLMClient, config: Dict[str, Any]) -> None:
        self.llm = llm
        self.sampling = config["vllm"]["sampling"]["explanation"]

    def run(
        self,
        sample: SampleRecord,
        parse: ParseRecord,
        diagnosis: DiagnosisRecord,
    ) -> DiagnosisRecord:
        payload = {
            "sample": sample.to_dict(),
            "parse": parse.to_dict(),
            "diagnosis": diagnosis.to_dict(),
        }
        messages = [
            {
                "role": "system",
                "content": "你是数学老师。只输出 JSON，不要 Markdown，解释必须具体、可验证、避免空泛评价。",
            },
            {
                "role": "user",
                "content": (
                    "请解释学生错误原因，指出证据片段，并给出一个可执行修正提示。"
                    "输出 JSON schema: {"
                    "\"pred_error_explanation\": string, "
                    "\"evidence_spans\": array[string], "
                    "\"repair_hint\": string"
                    "}。\n"
                    f"输入:\n{compact_dict(payload)}"
                ),
            },
        ]
        content = self.llm.chat(messages, self.sampling, response_format={"type": "json_object"})
        data = extract_json_object(content)
        diagnosis.pred_error_explanation = str(data.get("pred_error_explanation", ""))
        evidence = data.get("evidence_spans", [])
        diagnosis.evidence_spans = [str(x) for x in evidence] if isinstance(evidence, list) else []
        diagnosis.repair_hint = str(data.get("repair_hint", ""))
        diagnosis.raw["explanation"] = data
        return diagnosis
