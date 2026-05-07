from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


JsonDict = Dict[str, Any]


@dataclass
class SampleRecord:
    sample_id: str
    subset: str = ""
    question: str = ""
    answer: str = ""
    solution: str = ""
    student_answer: str = ""
    student_scratchwork_path: str = ""
    gold_error_category: str = ""
    gold_error_explanation: str = ""

    @classmethod
    def from_mapping(cls, data: JsonDict) -> "SampleRecord":
        sample_id = str(
            data.get("sample_id")
            or data.get("id")
            or data.get("question_id")
            or data.get("qid")
            or "sample"
        )
        return cls(
            sample_id=sample_id,
            subset=str(data.get("subset", "")),
            question=str(data.get("question", "")),
            answer=str(data.get("answer", "")),
            solution=str(data.get("solution", "")),
            student_answer=str(data.get("student_answer", "")),
            student_scratchwork_path=str(
                data.get("student_scratchwork_path")
                or data.get("student_scratchwork")
                or data.get("image_path")
                or ""
            ),
            gold_error_category=str(
                data.get("gold_error_category") or data.get("error_category") or ""
            ),
            gold_error_explanation=str(
                data.get("gold_error_explanation") or data.get("error_explanation") or ""
            ),
        )

    def to_dict(self) -> JsonDict:
        return asdict(self)

    def to_inference_dict(self) -> JsonDict:
        return {
            "sample_id": self.sample_id,
            "subset": self.subset,
            "question": self.question,
            "image_path": self.student_scratchwork_path,
        }

    def input_only(self) -> "SampleRecord":
        return SampleRecord(
            sample_id=self.sample_id,
            subset=self.subset,
            question=self.question,
            student_scratchwork_path=self.student_scratchwork_path,
        )


@dataclass
class ParseRecord:
    sample_id: str
    ocr_lines: List[str] = field(default_factory=list)
    detected_regions: List[JsonDict] = field(default_factory=list)
    formula_candidates: List[str] = field(default_factory=list)
    visual_features: JsonDict = field(default_factory=dict)
    parse_confidence: float = 0.0
    raw: JsonDict = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class DiagnosisRecord:
    sample_id: str
    pred_error_category: str
    category_probs: Dict[str, float] = field(default_factory=dict)
    pred_error_explanation: str = ""
    evidence_regions: List[Any] = field(default_factory=list)
    evidence_spans: List[str] = field(default_factory=list)
    repair_hint: str = ""
    raw: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class FeedbackRecord:
    sample_id: str
    student_feedback: str
    next_step_advice: str = ""
    teacher_summary: str = ""
    raw: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class RoundRecord:
    round_index: int
    name: str
    input: JsonDict = field(default_factory=dict)
    output: JsonDict = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class AgentResult:
    sample: SampleRecord
    parse: ParseRecord
    diagnosis: DiagnosisRecord
    feedback: FeedbackRecord
    student_work: JsonDict = field(default_factory=dict)
    reference_solution: JsonDict = field(default_factory=dict)
    rounds: List[RoundRecord] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return {
            "input": self.sample.to_inference_dict(),
            "sample": self.sample.to_inference_dict(),
            "rounds": [round_record.to_dict() for round_record in self.rounds],
            "parse": self.parse.to_dict(),
            "student_work": self.student_work,
            "reference_solution": self.reference_solution,
            "diagnosis": self.diagnosis.to_dict(),
            "feedback": self.feedback.to_dict(),
            "final": {
                "pred_error_category": self.diagnosis.pred_error_category,
                "pred_error_explanation": self.diagnosis.pred_error_explanation,
                "repair_hint": self.diagnosis.repair_hint,
                "student_feedback": self.feedback.student_feedback,
                "next_step_advice": self.feedback.next_step_advice,
                "teacher_summary": self.feedback.teacher_summary,
            },
            "errors": self.errors,
        }
