from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd


CATEGORY_NAMES = {
    0: "计算错误",
    1: "题目理解错误",
    2: "知识点错误",
    3: "答题技巧错误",
    4: "手写誊抄错误",
    5: "逻辑推理错误",
    6: "注意力与细节错误",
}


def safe_name(value: Any) -> str:
    text = str(value or "sample")
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text).strip("._-")
    return text or "sample"


def extract_image_bytes(value: Any) -> bytes:
    if isinstance(value, dict):
        data = value.get("bytes")
        if isinstance(data, bytes):
            return data
        path = value.get("path")
        if path:
            return Path(path).read_bytes()
    if isinstance(value, bytes):
        return value
    raise TypeError(f"unsupported image payload type: {type(value)!r}")


def iter_split(source_root: Path, split: str) -> Iterable[Dict[str, Any]]:
    parquet_path = source_root / split / "data-00000-of-00001.parquet"
    df = pd.read_parquet(parquet_path)
    for _, row in df.iterrows():
        yield row.to_dict()


def prepare_split(source_root: Path, out_root: Path, split: str) -> List[Dict[str, Any]]:
    image_dir = out_root / "images" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for item in iter_split(source_root, split):
        qid = str(item["question_id"])
        image_path = image_dir / f"{safe_name(qid)}.png"
        if not image_path.exists():
            image_path.write_bytes(extract_image_bytes(item["student_scratchwork"]))
        try:
            category_id = int(item["error_category"])
        except Exception:
            category_id = -1
        rows.append(
            {
                "sample_id": f"{split}-{qid}",
                "subset": split,
                "question": str(item.get("question", "")),
                "answer": str(item.get("answer", "")),
                "solution": str(item.get("solution", "")),
                "student_answer": str(item.get("student_answer", "")),
                "student_scratchwork_path": str(image_path),
                "gold_error_category": CATEGORY_NAMES.get(category_id, str(item.get("error_category", ""))),
                "gold_error_explanation": str(item.get("error_explanation", "")),
                "error_category_id": category_id,
                "question_id": qid,
            }
        )
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def to_inference_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sample_id": row["sample_id"],
        "subset": row["subset"],
        "question": row["question"],
        "image_path": row["student_scratchwork_path"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare ScratchMath parquet files for the agent CLI")
    parser.add_argument("--source-root", default="/data2/social_workspace/datasets/scratchmath")
    parser.add_argument("--out-root", default="/data2/social_workspace/datasets/scratchmath_agent")
    parser.add_argument("--splits", nargs="+", default=["primary", "middle"])
    args = parser.parse_args()

    source_root = Path(args.source_root)
    out_root = Path(args.out_root)
    all_rows: List[Dict[str, Any]] = []
    all_inference_rows: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"source_root": str(source_root), "out_root": str(out_root), "splits": {}}
    for split in args.splits:
        rows = prepare_split(source_root, out_root, split)
        inference_rows = [to_inference_row(row) for row in rows]
        count = write_jsonl(out_root / f"{split}.jsonl", rows)
        inference_count = write_jsonl(out_root / f"{split}_inference.jsonl", inference_rows)
        all_rows.extend(rows)
        all_inference_rows.extend(inference_rows)
        summary["splits"][split] = {
            "samples": count,
            "jsonl": str(out_root / f"{split}.jsonl"),
            "inference_jsonl": str(out_root / f"{split}_inference.jsonl"),
            "images_dir": str(out_root / "images" / split),
        }
        if inference_count != count:
            raise RuntimeError(f"inference count mismatch for {split}: {inference_count} != {count}")
    summary["all_jsonl"] = str(out_root / "all.jsonl")
    summary["all_inference_jsonl"] = str(out_root / "all_inference.jsonl")
    summary["total_samples"] = write_jsonl(out_root / "all.jsonl", all_rows)
    write_jsonl(out_root / "all_inference.jsonl", all_inference_rows)
    (out_root / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
