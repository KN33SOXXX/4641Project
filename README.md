# ScratchMath Homework Feedback Agent

This directory contains only the core agent files. Datasets, models, caches, logs,
and experiment outputs live under `/data2/social_workspace`.

## Layout

- `agent.py`: CLI orchestration for single-sample, batch, and class analytics runs.
- `server.py`: small stdlib HTTP API for `/health`, `/diagnose`, `/batch`, `/analytics`.
- `skills/`: handwritten parsing, error classification, explanation, feedback, analytics.
- `services/ocr_service.py`: PaddlePaddle/PaddleOCR-VL background OCR service.
- `config.yaml`: vLLM, OCR, workspace, and sampling parameters.

## vLLM

The agent calls the OpenAI-compatible vLLM endpoint:

```text
http://127.0.0.1:10005/v1
model: qwen3.6-35b-a3b
```

Classification uses low-temperature deterministic sampling. Explanation and
feedback use slightly higher temperature for readable wording.

## OCR Service

Prepare dependencies in the `dl` conda env if needed:

```bash
/home/user/social/scripts/bootstrap_ocr_env.sh
```

Download the PaddleOCR-VL model from ModelScope into `/data2`:

```bash
/home/user/social/scripts/download_ocr_model.sh
```

Start PaddleOCR-VL as a resident background service:

```bash
/home/user/social/scripts/start_ocr_tmux.sh
curl http://127.0.0.1:10004/health
```

Stop it:

```bash
/home/user/social/scripts/stop_ocr_service.sh
```

The service stores model/cache files in `/data2/social_workspace`, not `/home`.

## Dataset

Download ScratchMath from Hugging Face through a mirror:

```bash
/home/user/social/scripts/download_scratchmath_dataset.sh
```

Prepare agent-ready JSONL files and extracted scratchwork images:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/prepare_scratchmath_dataset.py
```

Prepared files are written under `/data2/social_workspace/datasets/scratchmath_agent`.
Use `*_inference.jsonl` for agent runs; those files contain only `question` and
`image_path`. The full `*.jsonl` files keep gold labels for offline evaluation.

## CLI

Health check:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
python3 agent.py health
```

Single sample:

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
python3 agent.py diagnose --question "题目文本" --image /path/to/scratchwork.png \
  --out /data2/social_workspace/outputs/diagnosis/sample_result.json
```

Batch JSONL:

```bash
python3 agent.py batch --input /path/to/samples.jsonl \
  --out /data2/social_workspace/outputs/diagnosis/results.jsonl
```

Class analytics:

```bash
python3 agent.py analytics --input /data2/social_workspace/outputs/diagnosis/results.jsonl \
  --out /data2/social_workspace/outputs/analytics/class_report.json
```

Virtual-student social report:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/build_student_social_report.py \
  --input /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --out-dir /data2/social_workspace/outputs/social_report_graph_feedback
```

This assigns primary samples to 200 virtual students and middle samples to 50
middle virtual students, then writes JSON artifacts, independent primary/middle
student similarity graphs with community detection, and an animated offline HTML report.

## Sample JSON

```json
{
  "sample_id": "demo-001",
  "subset": "primary",
  "question": "题目文本",
  "image_path": "/data2/social_workspace/datasets/scratchmath_agent/images/primary/demo.png"
}
```

The output includes a `rounds` array:

1. `handwritten_parsing`: OCR and formula extraction from the image.
2. `student_work_extraction`: student steps and final answer inferred from OCR.
3. `reference_solution`: independent solution generated from the question only.
4. `scratchwork_diagnosis`: comparison, error category, evidence, repair hint.
5. `feedback_generation`: builds an `analysis_graph` from rounds 1-4, reasons over that graph, then returns student feedback and teacher summary.

## Detailed Usage

### 1. Current Remote Configuration

The current remote deployment uses these concrete paths and ports:

| Item | Value |
| --- | --- |
| Core project | `/home/user/social` |
| Heavy workspace | `/data2/social_workspace` |
| Python env | `/home/user/miniconda3/envs/dl/bin/python` |
| vLLM endpoint | `http://127.0.0.1:10005/v1` |
| vLLM model name | `qwen3.6-35b-a3b` |
| OCR endpoint | `http://127.0.0.1:10004` |
| OCR model | `PaddlePaddle/PaddleOCR-VL` |
| OCR model dir | `/data2/social_workspace/models/PaddleOCR-VL` |
| OCR tmux session | `social_ocr` |
| Prepared dataset | `/data2/social_workspace/datasets/scratchmath_agent` |
| Full graph-feedback output | `/data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl` |
| Latest HTML report | `/data2/social_workspace/outputs/social_report_graph_feedback/report.html` |

The agent should call `127.0.0.1:10005` on the remote machine. Do not replace it with `10.123.4.20` inside the remote config, because the vLLM port is reached through port forwarding.

### 2. Proxy Rules For Inference

Before health checks or agent inference, clear HTTP proxy variables:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export no_proxy="127.0.0.1,localhost,10.123.4.20"
export NO_PROXY="$no_proxy"
```

This is important for `agent.py health`, `agent.py diagnose`, `agent.py batch`, and `regenerate_graph_feedback.py`.

### 3. OCR Service Lifecycle

Install or verify OCR dependencies:

```bash
bash /home/user/social/scripts/bootstrap_ocr_env.sh
```

Download the PaddleOCR-VL model from ModelScope:

```bash
bash /home/user/social/scripts/download_ocr_model.sh
```

Start OCR as a resident tmux service:

```bash
bash /home/user/social/scripts/start_ocr_tmux.sh
```

Check OCR status:

```bash
tmux ls | grep social_ocr
curl http://127.0.0.1:10004/health
tail -f /data2/social_workspace/logs/ocr_service.log
```

Stop OCR:

```bash
bash /home/user/social/scripts/stop_ocr_service.sh
```

### 4. Health Check

Run the combined health check:

```bash
bash /home/user/social/scripts/check_health.sh
```

Or run the CLI directly:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py health
```

The expected checks are:

- vLLM `/models` is reachable at `127.0.0.1:10005`.
- The vLLM model name is `qwen3.6-35b-a3b`.
- OCR is reachable at `127.0.0.1:10004`.
- OCR reports that the model is loaded.

### 5. Dataset Preparation

Download ScratchMath on the remote server through the Hugging Face mirror:

```bash
HF_ENDPOINT=https://hf-mirror.com \
bash /home/user/social/scripts/download_scratchmath_dataset.sh
```

Raw files are stored in:

```text
/data2/social_workspace/datasets/scratchmath
```

Prepare agent-ready JSONL files and extracted images:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/prepare_scratchmath_dataset.py
```

Prepared outputs:

```text
/data2/social_workspace/datasets/scratchmath_agent
├── all.jsonl
├── all_inference.jsonl
├── primary.jsonl
├── primary_inference.jsonl
├── middle.jsonl
├── middle_inference.jsonl
├── one_primary_inference.json
├── manifest.json
└── images/
```

Use `*_inference.jsonl` for normal inference. These files contain only the fields required by the agent, mainly `question` and `image_path`. Use the full `*.jsonl` files when gold labels are needed for offline evaluation.

### 6. Input Contract

The formal agent input is question plus image. `sample_id` and `subset` are optional but useful for tracking and reporting.

```json
{
  "sample_id": "demo-001",
  "subset": "primary",
  "question": "一个等腰梯形的周长是120厘米，两腰之和比上下底之和少10厘米，高是20厘米，这个梯形面积是___1___平方厘米。",
  "image_path": "/data2/social_workspace/datasets/scratchmath_agent/images/primary/demo.png"
}
```

Required fields:

- `question`: problem text.
- `image_path`: path to the student scratchwork image.

Optional fields:

- `sample_id`: stable ID for tracing.
- `subset`: `primary` or `middle`, used by downstream group reports.

### 7. Single-Sample Inference

Run from a JSON sample:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py diagnose \
  --sample /data2/social_workspace/datasets/scratchmath_agent/one_primary_inference.json \
  --out /data2/social_workspace/outputs/diagnosis/one_primary_graph_feedback.json
```

Run with inline question and image:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py diagnose \
  --question "题目文本" \
  --image /path/to/scratchwork.png \
  --sample-id demo-001 \
  --out /data2/social_workspace/outputs/diagnosis/demo_result.json
```

### 8. Full Dataset Inference

Input:

```text
/data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl
```

Recommended output:

```text
/data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl
```

Foreground run:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py batch \
  --input /data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl \
  --out /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --resume
```

Background tmux run:

```bash
tmux new-session -d -s graph_feedback_full 'cd /home/user/social && unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY && /home/user/miniconda3/envs/dl/bin/python agent.py batch --input /data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl --out /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl --resume 2>&1 | tee -a /data2/social_workspace/logs/scratchmath_graph_feedback_full.log'
```

Check progress:

```bash
tmux attach -t graph_feedback_full
wc -l /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl
tail -f /data2/social_workspace/logs/scratchmath_graph_feedback_full.log
```

Small smoke test:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py batch \
  --input /data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl \
  --out /data2/social_workspace/outputs/diagnosis/scratchmath_graph_feedback_limit3.jsonl \
  --limit 3
```

### 9. Regenerate Only Skill 5

If rounds 1-4 already exist in an older output, keep those results and rerun only graph feedback:

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/regenerate_graph_feedback.py \
  --input /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_10005.jsonl \
  --out /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --resume
```

Background tmux run:

```bash
tmux new-session -d -s graph_feedback_regen 'cd /home/user/social && unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY && PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python /home/user/social/scripts/regenerate_graph_feedback.py --input /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_10005.jsonl --out /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl --resume 2>&1 | tee -a /data2/social_workspace/logs/scratchmath_graph_feedback_regen.log'
```

### 10. Result Format

Each JSONL row contains:

- `input`: original input.
- `sample`: normalized sample object.
- `rounds`: all 5 skill rounds with round inputs and outputs.
- `final`: flattened diagnosis and feedback fields for quick downstream use.
- `errors`: collected runtime errors. A clean row has an empty array.

Important skill-5 fields:

```text
rounds[4].output.raw.analysis_graph
rounds[4].output.raw.graph_reasoning_summary
rounds[4].output.student_feedback
rounds[4].output.next_step_advice
rounds[4].output.teacher_summary
```

### 11. Student Social Graph And HTML Report

Generate virtual-student aggregation, independent primary/middle graphs, community detection, and HTML visualization:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/build_student_social_report.py \
  --input /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --out-dir /data2/social_workspace/outputs/social_report_graph_feedback
```

The report step currently:

- Assigns primary samples to `200` virtual students.
- Assigns middle samples to `50` virtual students.
- Aggregates student-level error rate, dominant error category, risk score, and representative feedback.
- Builds separate primary and middle student similarity graphs.
- Runs community detection and graph analysis.
- Produces an animated offline HTML report.

Optional graph controls:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/build_student_social_report.py \
  --input /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --out-dir /data2/social_workspace/outputs/social_report_graph_feedback \
  --max-neighbors 8 \
  --min-similarity 0.55 \
  --seed 20260430
```

Main report outputs:

```text
/data2/social_workspace/outputs/social_report_graph_feedback
├── report.html
├── assigned_results.jsonl
├── student_profiles.json
├── student_similarity_graph.json
├── primary_student_similarity_graph.json
├── middle_student_similarity_graph.json
└── group_summary.json
```

### 12. Quick Validation

Check the full inference row count:

```bash
wc -l /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl
```

Check generated report artifacts:

```bash
find /data2/social_workspace/outputs/social_report_graph_feedback -maxdepth 1 -type f | sort
```

Check primary/middle student counts:

```bash
/home/user/miniconda3/envs/dl/bin/python - <<'PY'
import json
from pathlib import Path
profiles = json.loads(Path('/data2/social_workspace/outputs/social_report_graph_feedback/student_profiles.json').read_text())
print('primary', sum(1 for p in profiles if p.get('group') == 'primary'))
print('middle', sum(1 for p in profiles if p.get('group') == 'middle'))
PY
```

Check graph summary:

```bash
/home/user/miniconda3/envs/dl/bin/python - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path('/data2/social_workspace/outputs/social_report_graph_feedback/group_summary.json').read_text())
for group, data in summary['groups'].items():
    graph = data['graph_analysis']
    print(group, 'students=', data['student_count'], 'communities=', graph['community_count'], 'components=', graph['component_count'], 'density=', graph['density'])
PY
```

## StudyClawHub Publishing

The project is organized for StudyClawHub as a single GitHub repository with separate Skill and Agent folders under `.claude`.

### Publishable folders

Skills:

```text
.claude/skills/scratchmath-handwritten-parsing
.claude/skills/scratchmath-student-work-extraction
.claude/skills/scratchmath-reference-solution
.claude/skills/scratchmath-scratchwork-diagnosis
.claude/skills/scratchmath-graph-feedback-generation
```

Agent:

```text
.claude/agents/scratchmath-homework-feedback-agent
```

### Registration metadata

Use `studyclawhub_submission.md` as the source of truth when filling StudyClawHub website fields:

- `name`
- `description`
- `version`
- `tags`
- `GitHub repo URL`
- `author`
- `Path to Skill Folder` or `Path to Agent Folder`

Before registration, replace:

```text
TODO_REPO_URL
TODO_AUTHOR
TODO_GITHUB_USERNAME
```

### GitHub packaging rules

Do publish:

- core Python files in `/home/user/social`
- `skills/`, `services/`, `scripts/`
- `.claude/skills/*/SKILL.md`
- `.claude/agents/*/AGENT.md`
- README and requirements files

Do not publish:

- `/data2/social_workspace`
- `social_workspace` symlink target
- datasets
- OCR/model weights
- cache files
- logs
- generated outputs

The `.gitignore` and `.clawhubignore` files are configured to keep these heavy runtime artifacts out of GitHub and StudyClawHub bundles.

### Suggested submission order

1. Push this repository to GitHub after replacing the `TODO_*` metadata values.
2. Each member submits their individual Skill on StudyClawHub using the corresponding `.claude/skills/<skill-name>` path.
3. The group submits the integrated Agent using `.claude/agents/scratchmath-homework-feedback-agent`.
4. Register the same version, `0.1.0`, for all initial submissions unless the team decides to version components independently.

### 13. Troubleshooting

If vLLM is unreachable, confirm `config.yaml`:

```yaml
vllm:
  base_url: http://127.0.0.1:10005/v1
  model: qwen3.6-35b-a3b
```

Then clear proxies and run:

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python /home/user/social/agent.py health
```

If OCR is unreachable:

```bash
tmux ls | grep social_ocr
tail -100 /data2/social_workspace/logs/ocr_service.log
curl http://127.0.0.1:10004/health
```

If a full batch run is interrupted, rerun the same `agent.py batch` command with `--resume`. The CLI will skip existing sample IDs in the output JSONL.

## 中文详细使用说明

这一节按实际使用顺序写，适合从远程机器上直接操作。

### 1. 先确认当前服务和目录

核心代码只放在：

```text
/home/user/social
```

大文件统一放在：

```text
/data2/social_workspace
```

当前关键服务：

```text
vLLM: http://127.0.0.1:10005/v1
model: qwen3.6-35b-a3b
OCR:  http://127.0.0.1:10004
OCR tmux: social_ocr
```

推理时远程 Agent 连接的是 `localhost:10005`，不是 `10.123.4.20:10005`。

### 2. 每次推理前取消代理

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export no_proxy="127.0.0.1,localhost,10.123.4.20"
export NO_PROXY="$no_proxy"
```

这是必须步骤。否则 Agent 访问本机 vLLM 或 OCR 服务时可能会走 HTTP 代理。

### 3. 启动 OCR 后台服务

如果 OCR 模型还没下载：

```bash
bash /home/user/social/scripts/download_ocr_model.sh
```

启动 PaddleOCR-VL 常驻服务：

```bash
bash /home/user/social/scripts/start_ocr_tmux.sh
```

检查是否启动成功：

```bash
tmux ls | grep social_ocr
curl http://127.0.0.1:10004/health
```

查看 OCR 日志：

```bash
tail -f /data2/social_workspace/logs/ocr_service.log
```

停止 OCR：

```bash
bash /home/user/social/scripts/stop_ocr_service.sh
```

### 4. 检查 Agent 健康状态

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py health
```

如果这里失败，优先检查：

- `config.yaml` 里的 vLLM 端口是否是 `10005`
- OCR `10004` 是否健康
- 是否已经取消代理
- vLLM 的 model name 是否是 `qwen3.6-35b-a3b`

### 5. 准备数据集

优先在远程用 Hugging Face 镜像站下载 ScratchMath：

```bash
HF_ENDPOINT=https://hf-mirror.com \
bash /home/user/social/scripts/download_scratchmath_dataset.sh
```

下载后的原始数据在：

```text
/data2/social_workspace/datasets/scratchmath
```

转换成 Agent 输入格式：

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/prepare_scratchmath_dataset.py
```

转换后的主要输入文件：

```text
/data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl
/data2/social_workspace/datasets/scratchmath_agent/primary_inference.jsonl
/data2/social_workspace/datasets/scratchmath_agent/middle_inference.jsonl
```

正式推理建议使用 `*_inference.jsonl`。这些文件只保留 Agent 需要的输入字段，也就是题目和图片。

### 6. 单题推理

使用准备好的单题 JSON：

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py diagnose \
  --sample /data2/social_workspace/datasets/scratchmath_agent/one_primary_inference.json \
  --out /data2/social_workspace/outputs/diagnosis/one_primary_graph_feedback.json
```

或者直接输入题目和图片：

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py diagnose \
  --question "题目文本" \
  --image /path/to/scratchwork.png \
  --sample-id demo-001 \
  --out /data2/social_workspace/outputs/diagnosis/demo_result.json
```

### 7. 完整数据集推理

完整输入：

```text
/data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl
```

完整输出：

```text
/data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl
```

前台运行：

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
/home/user/miniconda3/envs/dl/bin/python agent.py batch \
  --input /data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl \
  --out /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --resume
```

后台运行：

```bash
tmux new-session -d -s graph_feedback_full 'cd /home/user/social && unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY && /home/user/miniconda3/envs/dl/bin/python agent.py batch --input /data2/social_workspace/datasets/scratchmath_agent/all_inference.jsonl --out /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl --resume 2>&1 | tee -a /data2/social_workspace/logs/scratchmath_graph_feedback_full.log'
```

查看是否跑完：

```bash
wc -l /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl
tail -f /data2/social_workspace/logs/scratchmath_graph_feedback_full.log
```

如果中断，重复同一条 `agent.py batch` 命令并保留 `--resume`。

### 8. 只重跑第 5 个 skill

如果已经有旧结果，只想更新基于图分析的 feedback：

```bash
cd /home/user/social
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/regenerate_graph_feedback.py \
  --input /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_10005.jsonl \
  --out /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --resume
```

这个脚本不会重跑 OCR 和前 4 轮诊断，只会基于已有轮次构建 `analysis_graph` 并生成新的第 5 轮反馈。

### 9. 当前 5 个核心 skill

1. `handwritten_parsing`：读取图片，调用 PaddleOCR-VL，得到 OCR 文本、公式候选和解析置信度。
2. `student_work_extraction`：从 OCR 结果中提取学生最终答案、可见解题步骤、不确定点。
3. `reference_solution`：只根据题目生成参考答案、标准步骤和关键知识点。
4. `scratchwork_diagnosis`：比较学生作答和参考答案，判断错误类型、证据和修正提示。
5. `feedback_generation`：把前 4 轮结果组织成 `analysis_graph`，让模型先对图推理，再输出学生反馈、下一步建议和教师摘要。

第 5 轮的重要输出字段：

```text
rounds[4].output.raw.analysis_graph
rounds[4].output.raw.graph_reasoning_summary
rounds[4].output.student_feedback
rounds[4].output.next_step_advice
rounds[4].output.teacher_summary
```

### 10. 生成 social 图和 HTML 可视化

用完整 graph-feedback 结果生成学生级报告：

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/miniconda3/envs/dl/bin/python \
  /home/user/social/scripts/build_student_social_report.py \
  --input /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl \
  --out-dir /data2/social_workspace/outputs/social_report_graph_feedback
```

这个步骤会生成：

- `200` 个 primary 虚拟学生
- `50` 个 middle 虚拟学生
- 学生级错误率、风险分数、主要错误类型
- primary 和 middle 两张独立 social 图
- community detection 结果
- hub 学生、连通分量、图密度、相似度等图分析
- 动态 HTML 报告

输出位置：

```text
/data2/social_workspace/outputs/social_report_graph_feedback/report.html
/data2/social_workspace/outputs/social_report_graph_feedback/primary_student_similarity_graph.json
/data2/social_workspace/outputs/social_report_graph_feedback/middle_student_similarity_graph.json
/data2/social_workspace/outputs/social_report_graph_feedback/student_profiles.json
/data2/social_workspace/outputs/social_report_graph_feedback/group_summary.json
```

### 11. 快速验收

检查完整推理结果：

```bash
wc -l /data2/social_workspace/outputs/diagnosis/scratchmath_all_rounds_graph_feedback.jsonl
```

检查报告文件：

```bash
find /data2/social_workspace/outputs/social_report_graph_feedback -maxdepth 1 -type f | sort
```

检查学生数量：

```bash
/home/user/miniconda3/envs/dl/bin/python - <<'PY'
import json
from pathlib import Path
profiles = json.loads(Path('/data2/social_workspace/outputs/social_report_graph_feedback/student_profiles.json').read_text())
print('primary', sum(1 for p in profiles if p.get('group') == 'primary'))
print('middle', sum(1 for p in profiles if p.get('group') == 'middle'))
PY
```

检查图分析摘要：

```bash
/home/user/miniconda3/envs/dl/bin/python - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path('/data2/social_workspace/outputs/social_report_graph_feedback/group_summary.json').read_text())
for group, data in summary['groups'].items():
    graph = data['graph_analysis']
    print(group, 'students=', data['student_count'], 'communities=', graph['community_count'], 'components=', graph['component_count'], 'density=', graph['density'])
PY
```
