---
name: scratchmath-homework-feedback-agent
description: Integrates five ScratchMath skills into a question-plus-image agent for OCR, student work extraction, reference solving, diagnosis, graph feedback, and social report generation.
version: 0.1.0
author: ScratchMath Team (Yehua Huang, Jiayu Chen, Ningyuan Xiao, Qixiang Hua, Xiaofeng Li)
github_username: KN33SOXXX
repo_url: https://github.com/KN33SOXXX/4641Project
tags: [education, math, homework-feedback, social-network-mining, multi-skill-agent]
metadata: {"openclaw":{"requires":{"bins":["python","bash","curl"],"config":["config.yaml"]},"homepage":"https://github.com/KN33SOXXX/4641Project"}}
---

# ScratchMath Homework Feedback Agent

This agent diagnoses math homework from a question plus a student scratchwork image. It is implemented by `agent.py` as `ScratchMathFeedbackAgent`.

## Integrated Skills

1. `scratchmath-handwritten-parsing`: OCR and formula extraction from the image.
2. `scratchmath-student-work-extraction`: student answer and visible step extraction.
3. `scratchmath-reference-solution`: independent solution from the question only.
4. `scratchmath-scratchwork-diagnosis`: evidence-based error diagnosis.
5. `scratchmath-graph-feedback-generation`: analysis-graph reasoning and feedback.

## Runtime Services

- vLLM endpoint: `http://127.0.0.1:10005/v1`.
- vLLM model: `qwen3.6-35b-a3b`.
- OCR endpoint: `http://127.0.0.1:10004`.
- OCR model: `PaddlePaddle/PaddleOCR-VL`.
- Heavy workspace: `/data2/social_workspace`.

## Input Contract

The core agent input is:

- `question`: math problem text.
- `image_path`: path to the student scratchwork image.

Optional tracking fields:

- `sample_id`: stable sample ID.
- `subset`: `primary` or `middle`.

## Output Contract

Each result includes:

- `rounds`: five round records with round inputs and outputs.
- `final`: flattened diagnosis and feedback fields.
- `errors`: collected warnings or exceptions.

Round 5 includes `analysis_graph` and `graph_reasoning_summary` so downstream users can inspect the evidence path used to produce feedback.

## Common Commands

Health check:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py health
```

Single sample:

```bash
/home/user/miniconda3/envs/dl/bin/python agent.py diagnose \
  --sample /data2/social_workspace/datasets/scratchmath_agent/one_primary_inference.json \
  --out /data2/social_workspace/outputs/diagnosis/one_primary_graph_feedback.json
```

Full dataset:

```bash
/home/user/miniconda3/envs/dl/bin/python agent.py batch \
  --input /data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl \
  --out /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --resume
```

Student social report:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  scripts/build_student_social_report.py \
  --input /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --out-dir /data2/social_workspace/outputs/social_report_graph_feedback
```

## Publishing Notes

- Submit each component skill individually to StudyClawHub.
- Submit this agent as the group-level integration.
- Do not publish dataset files, OCR model weights, logs, cache files, or generated outputs.
- Metadata ready for StudyClawHub registration.

