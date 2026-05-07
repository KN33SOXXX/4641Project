---
name: scratchmath-homework-feedback-agent
description: Integrates five ScratchMath skills into a question-plus-image agent for OCR, student work extraction, reference solving, diagnosis, graph feedback, and social report generation.
version: 0.1.0
author: ScratchMath Team (Yehua Huang, Jiayu Chen, Ningyuan Xiao, Qixiang Hua, Xiaofeng Li)
tags: [education, math, homework-feedback, social-network-mining, multi-skill-agent]
---

# ScratchMath Homework Feedback Agent

This agent diagnoses math homework from a question plus a student scratchwork image.

## Child Skills

1. `scratchmath-handwritten-parsing` — OCR and formula extraction
2. `scratchmath-student-work-extraction` — Student answer and step extraction
3. `scratchmath-reference-solution` — Independent reference solution
4. `scratchmath-scratchwork-diagnosis` — Evidence-based error diagnosis
5. `scratchmath-graph-feedback-generation` — Graph reasoning and feedback
