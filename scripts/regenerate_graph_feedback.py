from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from agent import load_config  # noqa: E402
from schemas import DiagnosisRecord, FeedbackRecord, ParseRecord, SampleRecord  # noqa: E402
from services.vllm_client import VLLMClient  # noqa: E402
from skills.feedback_generation import FeedbackGenerationSkill  # noqa: E402


PROXY_ENV_VARS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")


def disable_proxy() -> None:
    for key in PROXY_ENV_VARS:
        os.environ.pop(key, None)
    os.environ["no_proxy"] = "127.0.0.1,localhost"
    os.environ["NO_PROXY"] = os.environ["no_proxy"]


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def to_parse_record(row: Dict[str, Any]) -> ParseRecord:
    payload = row.get("parse", {}) or {}
    return ParseRecord(
        sample_id=str(payload.get("sample_id") or row.get("input", {}).get("sample_id") or "sample"),
        ocr_lines=[str(item) for item in payload.get("ocr_lines", [])] if isinstance(payload.get("ocr_lines", []), list) else [],
        detected_regions=payload.get("detected_regions", []) if isinstance(payload.get("detected_regions", []), list) else [],
        formula_candidates=[str(item) for item in payload.get("formula_candidates", [])]
        if isinstance(payload.get("formula_candidates", []), list)
        else [],
        visual_features=payload.get("visual_features", {}) if isinstance(payload.get("visual_features", {}), dict) else {},
        parse_confidence=float(payload.get("parse_confidence", 0.0) or 0.0),
        raw=payload.get("raw", {}) if isinstance(payload.get("raw", {}), dict) else {},
        error=payload.get("error"),
    )


def to_diagnosis_record(row: Dict[str, Any]) -> DiagnosisRecord:
    payload = row.get("diagnosis", {}) or {}
    probs = payload.get("category_probs", {})
    if not isinstance(probs, dict):
        probs = {}
    return DiagnosisRecord(
        sample_id=str(payload.get("sample_id") or row.get("input", {}).get("sample_id") or "sample"),
        pred_error_category=str(payload.get("pred_error_category", "")),
        category_probs={str(key): float(value) for key, value in probs.items() if is_number(value)},
        pred_error_explanation=str(payload.get("pred_error_explanation", "")),
        evidence_regions=payload.get("evidence_regions", []) if isinstance(payload.get("evidence_regions", []), list) else [],
        evidence_spans=[str(item) for item in payload.get("evidence_spans", [])]
        if isinstance(payload.get("evidence_spans", []), list)
        else [],
        repair_hint=str(payload.get("repair_hint", "")),
        raw=payload.get("raw", {}) if isinstance(payload.get("raw", {}), dict) else {},
    )


def is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def regenerate_row(row: Dict[str, Any], skill: FeedbackGenerationSkill) -> Dict[str, Any]:
    sample = SampleRecord.from_mapping(row.get("input", {}) or row.get("sample", {})).input_only()
    parse = to_parse_record(row)
    diagnosis = to_diagnosis_record(row)
    student_work = row.get("student_work", {}) if isinstance(row.get("student_work", {}), dict) else {}
    reference_solution = (
        row.get("reference_solution", {}) if isinstance(row.get("reference_solution", {}), dict) else {}
    )
    analysis_graph = skill.build_analysis_graph(sample, parse, diagnosis, student_work, reference_solution)
    errors = list(row.get("errors", []))
    try:
        feedback = skill.run(
            sample,
            parse,
            diagnosis,
            student_work,
            reference_solution,
            analysis_graph=analysis_graph,
        )
        round_error = None
    except Exception as exc:
        round_error = str(exc)
        errors.append(f"graph feedback regeneration failed: {exc}")
        old = row.get("feedback", {}) if isinstance(row.get("feedback", {}), dict) else {}
        feedback = FeedbackRecord(
            sample_id=sample.sample_id,
            student_feedback=str(old.get("student_feedback", "")),
            next_step_advice=str(old.get("next_step_advice", "")),
            teacher_summary=str(old.get("teacher_summary", "")),
            raw={
                "analysis_graph": analysis_graph,
                "graph_reasoning_summary": "",
                "regeneration_error": str(exc),
                "previous_feedback": old,
            },
        )

    updated = json.loads(json.dumps(row, ensure_ascii=False))
    updated["feedback"] = feedback.to_dict()
    updated["final"] = {
        "pred_error_category": diagnosis.pred_error_category,
        "pred_error_explanation": diagnosis.pred_error_explanation,
        "repair_hint": diagnosis.repair_hint,
        "student_feedback": feedback.student_feedback,
        "next_step_advice": feedback.next_step_advice,
        "teacher_summary": feedback.teacher_summary,
    }
    rounds = updated.get("rounds", [])
    rounds = rounds[:4] if isinstance(rounds, list) else []
    rounds.append(
        {
            "round_index": 5,
            "name": "feedback_generation",
            "input": {"analysis_graph": analysis_graph},
            "output": feedback.to_dict(),
            "error": round_error,
        }
    )
    updated["rounds"] = rounds
    updated["errors"] = errors
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate only round-5 graph feedback from existing agent results")
    parser.add_argument("--input", default="/data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_10005.jsonl")
    parser.add_argument(
        "--out",
        default="/data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl",
    )
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    disable_proxy()
    rows = read_jsonl(Path(args.input))
    if args.limit > 0:
        rows = rows[: args.limit]
    out_path = Path(args.out)
    start_index = count_jsonl(out_path) if args.resume else 0
    if not args.resume:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("", encoding="utf-8")

    config = load_config(args.config)
    skill = FeedbackGenerationSkill(VLLMClient(config["vllm"]), config)
    total = len(rows)
    for index, row in enumerate(rows):
        if index < start_index:
            continue
        updated = regenerate_row(row, skill)
        append_jsonl(out_path, updated)
        sample_id = updated.get("input", {}).get("sample_id", f"row-{index}")
        graph = updated["rounds"][4]["input"]["analysis_graph"]
        print(
            f"[{index + 1}/{total}] {sample_id} errors={len(updated.get('errors', []))} "
            f"nodes={len(graph.get('nodes', []))} edges={len(graph.get('edges', []))}",
            file=sys.stderr,
            flush=True,
        )


if __name__ == "__main__":
    main()
