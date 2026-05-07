from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

sys.dont_write_bytecode = True

import yaml

from schemas import AgentResult, DiagnosisRecord, FeedbackRecord, RoundRecord, SampleRecord
from services.ocr_client import OCRClient
from services.vllm_client import VLLMClient
from skills import (
    ClassAnalyticsSkill,
    FeedbackGenerationSkill,
    HandwrittenParsingSkill,
    ReferenceSolutionSkill,
    ScratchworkDiagnosisSkill,
    StudentWorkExtractionSkill,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.yaml"
PROXY_ENV_VARS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")


def disable_http_proxy_env() -> None:
    for name in PROXY_ENV_VARS:
        os.environ.pop(name, None)
    os.environ["no_proxy"] = "127.0.0.1,localhost,10.123.4.20"
    os.environ["NO_PROXY"] = os.environ["no_proxy"]


def load_config(path: str | os.PathLike[str] = DEFAULT_CONFIG) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    ensure_workspace(config)
    return config


def ensure_workspace(config: Dict[str, Any]) -> None:
    for key, value in config.get("workspace", {}).items():
        if key.endswith("_dir") or key == "root":
            Path(value).mkdir(parents=True, exist_ok=True)


class ScratchMathFeedbackAgent:
    def __init__(self, config: Dict[str, Any]) -> None:
        disable_http_proxy_env()
        self.config = config
        self.llm = VLLMClient(config["vllm"])
        self.ocr = OCRClient(config["ocr"])
        self.parser = HandwrittenParsingSkill(self.ocr)
        self.student_work_extractor = StudentWorkExtractionSkill(self.llm, config)
        self.reference_solver = ReferenceSolutionSkill(self.llm, config)
        self.diagnoser = ScratchworkDiagnosisSkill(self.llm, config)
        self.feedback = FeedbackGenerationSkill(self.llm, config)
        self.analytics = ClassAnalyticsSkill(self.llm, config)

    def health(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {"workspace": self.config["workspace"], "vllm": {}, "ocr": {}}
        for name, fn in (("vllm", self.llm.health), ("ocr", self.ocr.health)):
            try:
                status[name] = {"ok": True, "detail": fn()}
            except Exception as exc:
                status[name] = {"ok": False, "error": str(exc)}
        return status

    def diagnose(self, sample_data: Dict[str, Any]) -> AgentResult:
        sample = SampleRecord.from_mapping(sample_data).input_only()
        errors: List[str] = []
        rounds: List[RoundRecord] = []

        parse = self.parser.run(sample)
        rounds.append(
            RoundRecord(
                round_index=1,
                name="handwritten_parsing",
                input=sample.to_inference_dict(),
                output=parse.to_dict(),
                error=parse.error,
            )
        )
        if parse.error:
            errors.append(f"OCR parse warning: {parse.error}")

        student_work: Dict[str, Any] = {}
        try:
            student_work = self.student_work_extractor.run(sample, parse)
            rounds.append(
                RoundRecord(
                    round_index=2,
                    name="student_work_extraction",
                    input={"question": sample.question, "parse": parse.to_dict()},
                    output=student_work,
                )
            )
        except Exception as exc:
            errors.append(f"student work extraction failed: {exc}")
            rounds.append(
                RoundRecord(
                    round_index=2,
                    name="student_work_extraction",
                    input={"question": sample.question, "parse": parse.to_dict()},
                    error=str(exc),
                )
            )

        reference_solution: Dict[str, Any] = {}
        try:
            reference_solution = self.reference_solver.run(sample)
            rounds.append(
                RoundRecord(
                    round_index=3,
                    name="reference_solution",
                    input={"question": sample.question},
                    output=reference_solution,
                )
            )
        except Exception as exc:
            errors.append(f"reference solution failed: {exc}")
            rounds.append(
                RoundRecord(
                    round_index=3,
                    name="reference_solution",
                    input={"question": sample.question},
                    error=str(exc),
                )
            )

        try:
            diagnosis = self.diagnoser.run(sample, parse, student_work, reference_solution)
            rounds.append(
                RoundRecord(
                    round_index=4,
                    name="scratchwork_diagnosis",
                    input={
                        "question": sample.question,
                        "parse": parse.to_dict(),
                        "student_work": student_work,
                        "reference_solution": reference_solution,
                    },
                    output=diagnosis.to_dict(),
                )
            )
        except Exception as exc:
            errors.append(f"scratchwork diagnosis failed: {exc}")
            fallback_category = self.config["agent"]["error_categories"][0]
            diagnosis = DiagnosisRecord(
                sample_id=sample.sample_id,
                pred_error_category=fallback_category,
                pred_error_explanation="",
                repair_hint="",
            )
            rounds.append(
                RoundRecord(
                    round_index=4,
                    name="scratchwork_diagnosis",
                    input={
                        "question": sample.question,
                        "parse": parse.to_dict(),
                        "student_work": student_work,
                        "reference_solution": reference_solution,
                    },
                    output=diagnosis.to_dict(),
                    error=str(exc),
                )
            )
        try:
            analysis_graph = self.feedback.build_analysis_graph(
                sample, parse, diagnosis, student_work, reference_solution
            )
            feedback = self.feedback.run(
                sample,
                parse,
                diagnosis,
                student_work,
                reference_solution,
                analysis_graph=analysis_graph,
            )
            rounds.append(
                RoundRecord(
                    round_index=5,
                    name="feedback_generation",
                    input={"analysis_graph": analysis_graph},
                    output=feedback.to_dict(),
                )
            )
        except Exception as exc:
            errors.append(f"feedback generation failed: {exc}")
            analysis_graph = self.feedback.build_analysis_graph(
                sample, parse, diagnosis, student_work, reference_solution
            )
            feedback = FeedbackRecord(
                sample_id=sample.sample_id,
                student_feedback="",
                next_step_advice="",
                teacher_summary="",
            )
            rounds.append(
                RoundRecord(
                    round_index=5,
                    name="feedback_generation",
                    input={"analysis_graph": analysis_graph},
                    output=feedback.to_dict(),
                    error=str(exc),
                )
            )
        return AgentResult(
            sample=sample,
            parse=parse,
            student_work=student_work,
            reference_solution=reference_solution,
            diagnosis=diagnosis,
            feedback=feedback,
            rounds=rounds,
            errors=errors,
        )

    def diagnose_many(self, samples: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.diagnose(sample).to_dict() for sample in samples]

    def class_analytics(self, results: Iterable[Dict[str, Any]], with_llm_summary: bool = True) -> Dict[str, Any]:
        return self.analytics.run(results, with_llm_summary=with_llm_summary)


def read_json_or_jsonl(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        if path.endswith(".jsonl"):
            return [json.loads(line) for line in fh if line.strip()]
        return json.load(fh)


def write_json(path: str, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: str, row: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()


def count_jsonl_rows(path: str) -> int:
    if not Path(path).exists():
        return 0
    with open(path, "r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ScratchMath Homework Feedback Agent")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")

    diagnose = sub.add_parser("diagnose")
    diagnose.add_argument("--sample")
    diagnose.add_argument("--question")
    diagnose.add_argument("--image")
    diagnose.add_argument("--sample-id", default="sample")
    diagnose.add_argument("--out", required=True)

    batch = sub.add_parser("batch")
    batch.add_argument("--input", required=True)
    batch.add_argument("--out", required=True)
    batch.add_argument("--limit", type=int, default=0)
    batch.add_argument("--resume", action="store_true")

    analytics = sub.add_parser("analytics")
    analytics.add_argument("--input", required=True)
    analytics.add_argument("--out", required=True)
    analytics.add_argument("--no-llm-summary", action="store_true")
    return parser


def main() -> None:
    disable_http_proxy_env()
    args = build_arg_parser().parse_args()
    agent = ScratchMathFeedbackAgent(load_config(args.config))
    if args.command == "health":
        print(json.dumps(agent.health(), ensure_ascii=False, indent=2))
    elif args.command == "diagnose":
        if args.sample:
            sample = read_json_or_jsonl(args.sample)
            if isinstance(sample, list):
                if len(sample) != 1:
                    raise SystemExit("diagnose expects one JSON object or a JSONL file with one row")
                sample = sample[0]
        else:
            if not args.question or not args.image:
                raise SystemExit("diagnose expects --sample or both --question and --image")
            sample = {
                "sample_id": args.sample_id,
                "question": args.question,
                "image_path": args.image,
            }
        write_json(args.out, agent.diagnose(sample).to_dict())
    elif args.command == "batch":
        samples = read_json_or_jsonl(args.input)
        if not isinstance(samples, list):
            raise SystemExit("batch expects a JSON array or JSONL file")
        if args.limit > 0:
            samples = samples[: args.limit]
        start_index = count_jsonl_rows(args.out) if args.resume else 0
        if not args.resume:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text("", encoding="utf-8")
        total = len(samples)
        for index, sample in enumerate(samples):
            if index < start_index:
                continue
            result = agent.diagnose(sample).to_dict()
            append_jsonl(args.out, result)
            sample_id = result.get("input", {}).get("sample_id", f"row-{index}")
            error_count = len(result.get("errors", []))
            print(f"[{index + 1}/{total}] {sample_id} errors={error_count}", file=sys.stderr, flush=True)
    elif args.command == "analytics":
        rows = read_json_or_jsonl(args.input)
        if not isinstance(rows, list):
            raise SystemExit("analytics expects a JSON array or JSONL file")
        write_json(args.out, agent.class_analytics(rows, with_llm_summary=not args.no_llm_summary))


if __name__ == "__main__":
    main()
