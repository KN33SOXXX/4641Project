---
name: scratchmath-reference-solution
description: Generate an independent reference solution from ScratchMath question text only for later diagnosis.
version: 0.1.0
author: TODO_AUTHOR
github_username: TODO_GITHUB_USERNAME
repo_url: TODO_REPO_URL
tags: [education, math, solution-generation, qwen, reasoning]
metadata: {"openclaw":{"requires":{"bins":["python"],"config":["config.yaml"]},"homepage":"TODO_REPO_URL"}}
---

# ScratchMath Reference Solution

Use this skill when an agent needs a reference answer and compact solution path generated independently from the question, without looking at the student's OCR output or gold labels.

## Runtime Role

This skill is implemented by `skills/reference_solution.py` and called by `ScratchMathFeedbackAgent` as round 3. It uses low-variance sampling and JSON repair logic to keep the answer parseable.

## Input

- `sample_id`: stable sample identifier.
- `question`: math problem text.

## Output

- `reference_answer`: final answer string.
- `solution_steps`: short reference steps.
- `key_concepts`: up to three math concepts.
- `confidence`: 0 to 1 self-estimated confidence.
- `raw`: original model JSON.

## Operational Notes

- The prompt explicitly forbids using student answers or labels.
- The skill is designed to support diagnosis, not to grade by itself.
- Current model endpoint: `http://127.0.0.1:10005/v1`.

