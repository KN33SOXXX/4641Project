# StudyClawHub Submission Metadata

Metadata is ready for StudyClawHub registration.

## Repository

| Field | Value |
| --- | --- |
| GitHub repo URL | `https://github.com/KN33SOXXX/4641Project` |
| Author | `ScratchMath Team (Yehua Huang, Jiayu Chen, Ningyuan Xiao, Qixiang Hua, Xiaofeng Li)` |
| GitHub username | `KN33SOXXX` |
| Version | `0.1.0` |
| License | `MIT-0 compatible for submitted skill bundles` |

## Skills

| Name | Description | Version | Tags | Path to Skill Folder |
| --- | --- | --- | --- | --- |
| `scratchmath-handwritten-parsing` | OCR and visual parsing for handwritten ScratchMath solution images using a PaddleOCR-VL service. | `0.1.0` | `education, math, ocr, scratchwork, social-network-mining` | `.claude/skills/scratchmath-handwritten-parsing` |
| `scratchmath-student-work-extraction` | Extract student final answers, visible steps, uncertainty, and scratchwork summaries from OCR output. | `0.1.0` | `education, math, reasoning, scratchwork, diagnosis` | `.claude/skills/scratchmath-student-work-extraction` |
| `scratchmath-reference-solution` | Generate an independent reference solution from question text only for comparison and diagnosis. | `0.1.0` | `education, math, solution-generation, qwen, reasoning` | `.claude/skills/scratchmath-reference-solution` |
| `scratchmath-scratchwork-diagnosis` | Compare student work against the reference solution and classify the dominant error cause with evidence. | `0.1.0` | `education, math, error-diagnosis, feedback, assessment` | `.claude/skills/scratchmath-scratchwork-diagnosis` |
| `scratchmath-graph-feedback-generation` | Build an analysis graph from prior rounds and reason over it to generate student feedback and teacher summaries. | `0.1.0` | `education, graph-reasoning, feedback, social-network-mining, qwen` | `.claude/skills/scratchmath-graph-feedback-generation` |

## Agent

| Field | Value |
| --- | --- |
| Name | `scratchmath-homework-feedback-agent` |
| Description | Integrates five ScratchMath skills into a question-plus-image agent for OCR, student work extraction, reference solving, diagnosis, graph-based feedback, and social report generation. |
| Version | `0.1.0` |
| Tags | `education, math, homework-feedback, social-network-mining, multi-skill-agent` |
| Path to Agent Folder | `.claude/agents/scratchmath-homework-feedback-agent` |
| GitHub repo URL | `https://github.com/KN33SOXXX/4641Project` |
| Author | `ScratchMath Team (Yehua Huang, Jiayu Chen, Ningyuan Xiao, Qixiang Hua, Xiaofeng Li)` |

## Website Registration Checklist

1. Push this repository to GitHub after replacing `https://github.com/KN33SOXXX/4641Project`, `ScratchMath Team (Yehua Huang, Jiayu Chen, Ningyuan Xiao, Qixiang Hua, Xiaofeng Li)`, and `KN33SOXXX`.
2. On StudyClawHub, submit each skill individually with the corresponding folder path above.
3. Submit the integrated agent with `.claude/agents/scratchmath-homework-feedback-agent`.
4. Do not upload `/data2/social_workspace`, model weights, dataset files, logs, or generated outputs.

