### LLM Judge (web-agent evaluator)

Evaluates web browsing agents from a results folder. For each task directory, it reads a compressed (zst) or JSON results file plus screenshots, then produces a structured judgment:

- **score**: integer 0–100 (>=70 = success, <70 = failure)
- **observed issue codes**
- **insights and reasoning** for the score
- **improvement tips**

Supported models: any OpenAI (`gpt-*`) or Gemini (`gemini-*`) model. Recommended: **gpt-5** for best accuracy.

### Folder structure (brief)

- `src/neurosim/judge/evaluate_results.py`: CLI to evaluate a folder of tasks
- `src/neurosim/judge/judge_system.py`: scoring, reasoning, and output schema
- `src/neurosim/judge/adapters.py`: OpenAI/Gemini model adapters
- `src/neurosim/judge/messages.py`: system/user prompts for the judge
- `src/neurosim/judge/run_judge.sh`: convenience runner

Input expectations per task folder:
- Results file at top-level: `result.json|zst|zsp` or `results.json|zst|zsp`
- Screenshots: `screenshot_*.png`

### How to run (examples)

Environment variables:
- `OPENAI_API_KEY` or `GOOGLE_API_KEY` (required by chosen provider)
- `JUDGE_MAX_CONCURRENCY` (default 50; higher for faster throughput)
- `JUDGE_TASK_TIMEOUT_SECONDS` (optional; unset = no per-task timeout)

CLI flags:
- `eval_folder` (positional): path to an episode folder (or a single task folder)
- `--model MODEL` (default `gpt-4o`), e.g. `gpt-5`, `gemini-2.5-pro`
- `--max-images N` (default `10`): max screenshots per task
- `--output FILE` (default `llm_judge.json` inside the eval folder)

Quick start (recommended):

```bash
export OPENAI_API_KEY=...  # or GOOGLE_API_KEY=...
export JUDGE_MAX_CONCURRENCY=100
PYTHONPATH=/home/anaishowland/workspace/neurosim/judge/src \
python -m neurosim.judge.evaluate_results /path/to/{EVAL_FOLDER_OR_EPISODE} \
  --model gpt-5
```

User-provided example:

```bash
export JUDGE_MAX_CONCURRENCY=100 && \
PYTHONPATH=/home/anaishowland/workspace/neurosim/judge/src \
python -m neurosim.judge.evaluate_results \
  /home/anaishowland/data/01K3H6N0JRCF04GWQSZAP946G1/0 --model gpt-5
```

Using the helper script:

```bash
src/neurosim/judge/run_judge.sh /path/to/{EVAL_FOLDER_OR_EPISODE} --model gpt-5 --max-images 10
```

Output:
- Aggregated JSON written to `llm_judge.json` in the target folder (or `--output` path)


