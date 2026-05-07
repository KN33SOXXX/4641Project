from __future__ import annotations

from typing import Any, Dict

from schemas import ParseRecord, SampleRecord
from services.ocr_client import OCRClient


class HandwrittenParsingSkill:
    def __init__(self, ocr_client: OCRClient) -> None:
        self.ocr_client = ocr_client

    def run(self, sample: SampleRecord) -> ParseRecord:
        if not sample.student_scratchwork_path:
            return ParseRecord(sample_id=sample.sample_id, error="missing scratchwork image")
        try:
            raw: Dict[str, Any] = self.ocr_client.parse_image(
                sample.student_scratchwork_path,
                sample_id=sample.sample_id,
                question=sample.question,
            )
            return ParseRecord(
                sample_id=sample.sample_id,
                ocr_lines=list(raw.get("ocr_lines", [])),
                detected_regions=list(raw.get("detected_regions", [])),
                formula_candidates=list(raw.get("formula_candidates", [])),
                visual_features=dict(raw.get("visual_features", {})),
                parse_confidence=float(raw.get("parse_confidence", 0.0)),
                raw=raw,
                error=raw.get("error"),
            )
        except Exception as exc:
            return ParseRecord(sample_id=sample.sample_id, error=str(exc))
