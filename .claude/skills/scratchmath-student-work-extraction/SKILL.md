---
name: scratchmath-student-work-extraction
description: Extract student final answers, visible steps, uncertainty, and scratchwork summaries from ScratchMath OCR output.
version: 0.1.0
author: Jiayu Chen
github_username: KN33SOXXX
repo_url: https://github.com/KN33SOXXX/4641Project
tags: [education, math, reasoning, scratchwork, diagnosis]
metadata: {"openclaw":{"requires":{"bins":["python"],"config":["config.yaml"]},"homepage":"https://github.com/KN33SOXXX/4641Project"}}
---

# ScratchMath Student Work Extraction

Use this skill after handwritten parsing when an agent needs to infer what the student wrote, what answer they likely gave, and which parts of the scratchwork remain uncertain.

## Runtime Role

This skill is implemented by `skills/student_work_extraction.py` and called by `ScratchMathFeedbackAgent` as round 2. It uses the configured OpenAI-compatible vLLM endpoint and returns strict JSON for downstream comparison.

## Input

- `question`: original math problem text.
- `parse`: the round-1 OCR parse record.

## Output

- `student_final_answer`: extracted answer when visible.
- `visible_steps`: ordered student step strings.
- `scratchwork_summary`: concise description of the work.
- `uncertain_points`: OCR or reasoning uncertainties.
- `confidence`: 0 to 1 extraction confidence.
- `raw`: original model JSON.

## Operational Notes

- The skill must not use gold labels or reference answers.
- It should only rely on the question text and OCR parse.
- The current deployment calls `http://127.0.0.1:10005/v1` with model `qwen3.6-35b-a3b`.
- HTTP proxy variables should be unset before inference.

