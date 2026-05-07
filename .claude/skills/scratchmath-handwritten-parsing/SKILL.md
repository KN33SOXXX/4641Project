---
name: scratchmath-handwritten-parsing
description: OCR and visual parsing for handwritten ScratchMath solution images using a resident PaddleOCR-VL service.
version: 0.1.0
author: Yehua Huang
github_username: KN33SOXXX
repo_url: https://github.com/KN33SOXXX/4641Project
tags: [education, math, ocr, scratchwork, social-network-mining]
metadata: {"openclaw":{"requires":{"bins":["python","curl"],"config":["config.yaml"]},"homepage":"https://github.com/KN33SOXXX/4641Project"}}
---

# ScratchMath Handwritten Parsing

Use this skill when an agent needs to read a student's handwritten scratchwork image for a ScratchMath-style math problem and convert it into structured OCR evidence for downstream diagnosis.

## Runtime Role

This skill is implemented by `skills/handwritten_parsing.py` and called by `ScratchMathFeedbackAgent` as round 1. It delegates image parsing to `services/ocr_client.py`, which expects a PaddleOCR-VL HTTP service at the OCR URL configured in `config.yaml`.

## Input

The skill receives a normalized sample with:

- `sample_id`: stable sample identifier.
- `question`: math problem text.
- `image_path`: path to the student scratchwork image.
- `subset`: optional group label such as `primary` or `middle`.

## Output

The skill returns a parse record with:

- `ocr_lines`: recognized text lines.
- `detected_regions`: visual regions when available.
- `formula_candidates`: formula-like OCR lines.
- `visual_features`: image size and OCR task metadata.
- `parse_confidence`: numeric confidence used by later rounds.
- `error`: OCR warning or service failure text.

## Operational Notes

- Start OCR before using this skill: `bash scripts/start_ocr_tmux.sh`.
- Check OCR health: `curl http://127.0.0.1:10004/health`.
- Keep model files under `/data2/social_workspace/models/PaddleOCR-VL`.
- Do not bundle model weights or dataset files in StudyClawHub submissions.

