---
name: scratchmath-scratchwork-diagnosis
description: Compare extracted student work against a reference solution and classify the dominant ScratchMath error cause with evidence.
version: 0.1.0
author: Qixiang Hua
github_username: KN33SOXXX
repo_url: https://github.com/KN33SOXXX/4641Project
tags: [education, math, error-diagnosis, feedback, assessment]
metadata: {"openclaw":{"requires":{"bins":["python"],"config":["config.yaml"]},"homepage":"https://github.com/KN33SOXXX/4641Project"}}
---

# ScratchMath Scratchwork Diagnosis

Use this skill when an agent has OCR evidence, extracted student work, and an independent reference solution, and needs a concrete error diagnosis for the student response.

## Runtime Role

This skill is implemented by `skills/scratchwork_diagnosis.py` and called by `ScratchMathFeedbackAgent` as round 4. It uses the error categories configured in `config.yaml`.

## Input

- `question`: original math problem.
- `scratchwork_ocr`: round-1 parse record.
- `student_work_extraction`: round-2 student work output.
- `reference_solution`: round-3 reference solution output.
- `allowed_categories`: configured diagnosis taxonomy.

## Output

- `pred_error_category`: one allowed category.
- `category_probs`: probability-like category scores.
- `pred_error_explanation`: diagnosis rationale.
- `evidence_regions`: coarse evidence references.
- `evidence_spans`: text spans supporting the diagnosis.
- `repair_hint`: concrete correction hint.

## Operational Notes

- The current categories include calculation, problem understanding, knowledge point, strategy, handwriting transcription, logic, attention/detail, and no-error cases.
- Keep diagnosis evidence tied to input fields so later graph feedback can trace the reasoning path.

