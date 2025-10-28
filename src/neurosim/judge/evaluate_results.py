#!/usr/bin/env python3
"""
This script is used to evaluate the results of the web browsing agent.
It is used to evaluate the results of the web browsing agent.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, get_args
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import zstandard as zstd

# Local imports
from neurosim.judge.judge_system import judge_with_retry
from neurosim.judge.adapter import OpenAIAdapter, GeminiAdapter
from neurosim.judge.model import AdapterRequest
from neurosim.judge.model import OpenAIModel, GeminiModel
from neurosim.judge.adapter import Adapter

from neurosim.constants import RESULT_FILE, JUDGE_RESULTS_FILE, JUDGE_MAX_CONCURRENCY, DELAY

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(name)s: %(message)s')
logger = logging.getLogger(__name__)


class EvaluatorRequest(BaseModel):
    """
    Request for an evaluator.
    """
    eval_folder: Path
    model: Union[OpenAIModel, GeminiModel]
    max_images: int
    output: Optional[str]
    temperature: Optional[float]


class EvaluatorResult(BaseModel):
    """
    Result for an evaluator.
    """
    task_id: str
    task_description: str
    model: Union[OpenAIModel, GeminiModel]
    llm_success: bool
    latency: int
    tokens: Dict[str, Any]
    steps_count: int
    screenshots_count: int
    agent_success: bool
    agent_results: str
    agent_error: str
    evaluation: Dict[str, Any]


class EvaluatorEpisodeResult(BaseModel):
    """
    Result for an evaluator episode.
    """
    episode: str
    total_tasks: int
    evaluations_completed: int
    evaluations_failed: int
    average_score: float
    llm_success_rate: float
    agent_success_rate: float
    evaluations: List[EvaluatorResult]
    errors: List[EvaluatorResult]
    final_result: Dict[str, Any]
    final_score: float
    final_success: bool
    final_error: str
    final_reasoning: str
    final_evaluation: Dict[str, Any]


class TaskResult(BaseModel):
    """
    Result for a task.

    Attributes:
        task_id: The ID of the task.
        task_description: The description of the task.
        model: The model used for the task.
        llm_success: Whether the LLM succeeded.
        latency: The latency of the task.
        tokens: The tokens of the task.
        steps_count: The number of steps in the task.
        screenshots_count: The number of screenshots in the task.
        agent_success: Whether the agent succeeded.
        agent_results: The results of the agent.
        agent_error: The error of the agent.
        evaluation: The evaluation of the task.

    Default values:
        llm_success: False
        latency: 0
        tokens: {}
        steps_count: 0
        screenshots_count: 0
        agent_success: False
        agent_results: "NA"
        agent_error: "NA"
        evaluation: {}
    """
    task_id: str = Field(default_factory=str,
                         description="The ID of the task.")
    task_description: str = Field(
        default_factory=str, description="The description of the task.")
    model: str = Field(
        default_factory=lambda: 'unknown',
        description="Agent model string (e.g., vertex_ai/gemini-2.5-flash).")
    llm_success: bool = Field(default_factory=bool,
                              description="Whether the LLM succeeded.")
    latency: float = Field(default_factory=float,
                           description="The latency of the task in seconds (float).")
    tokens: Any = Field(
        default_factory=list, description="Token usage details per model call.")
    steps_count: int = Field(default_factory=int,
                             description="The number of steps in the task.")
    screenshots_count: int = Field(
        default_factory=int, description="The number of screenshots in the task.")
    agent_success: bool = Field(default_factory=bool,
                                description="Whether the agent succeeded.")
    agent_results: str = Field(
        default_factory=str, description="The results of the agent.")
    agent_error: str = Field(default_factory=str,
                             description="The error of the agent.")
    evaluation: Dict[str, Any] = Field(default_factory=dict,
                                       description="The evaluation of the task.")
    judge_token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Judge-only token usage for this task: {prompt_tokens, completion_tokens, total_tokens}.")


class TaskError(BaseModel):
    """
    Error for a task.
    """
    task_id: str = Field(default_factory=str,
                         description="The ID of the task.")
    error: str = Field(default_factory=str,
                       description="The error of the task.")
    error_type: str = Field(default_factory=str,
                            description="The type of the error of the task.")
    error_message: str = Field(
        default_factory=str, description="The message of the error of the task.")


class EpisodeResult(BaseModel):
    """
    Result for an evaluator episode.
    """
    episode: str
    total_tasks: int
    evaluations_completed: int
    evaluations_failed: int
    average_score: float
    llm_success_rate: float
    agent_success_rate: float
    evaluations: List[TaskResult]
    errors: List[TaskResult]
    final_result: Dict[str, Any]
    final_score: float
    final_success: bool
    final_error: str
    final_reasoning: str
    final_evaluation: Dict[str, Any]


class Evaluator:
    """
    Evaluator for the web browsing agent.
    """

    def __init__(self, request: EvaluatorRequest):
        """
        Initialize the evaluator.
        """
        logger.info("Starting evaluation: %s", Path(request.eval_folder))
        self.eval_folder = request.eval_folder
        self.temperature = request.temperature
        self.max_images = request.max_images
        self.output = request.output
        self.adapter: Adapter = self._get_adapter(request.model)

    def _get_adapter(self, model: Union[OpenAIModel, GeminiModel]) -> Adapter:
        """
        Get the adapter for the model.
        """
        if model in get_args(OpenAIModel):
            return OpenAIAdapter(request=AdapterRequest(model=model, temperature=self.temperature))
        if model in get_args(GeminiModel):
            return GeminiAdapter(request=AdapterRequest(model=model, temperature=self.temperature))
        raise ValueError(f"Unsupported model: {model}")

    @staticmethod
    def _load_result_file(task_folder: Path) -> Optional[Dict[str, Any]]:
        """
        Load the result file from the task folder.
        """
        for name in (RESULT_FILE,):
            p = task_folder / name
            if p.exists():
                dctx = zstd.ZstdDecompressor()
                data = dctx.decompress(p.read_bytes())
                return json.loads(data.decode("utf-8"))
        return None

    def get_screenshots(self, task_folder: Path) -> List[str]:
        """
        Get the screenshots from the task folder.
        """
        paths = [str(p) for p in task_folder.glob("screenshot_*.png")]
        paths.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]))
        return paths

    def has_result_file(self, task_folder: Path) -> bool:
        """Check for presence of a result file without decompressing it."""
        return any((task_folder / name).exists()
                   for name in (RESULT_FILE,))

    def to_bool(self, value: Any) -> Optional[bool]:
        """
        Convert a value to a boolean.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "yes", "y", "1", "success"}:
                return True
            if v in {"false", "no", "n", "0", "failure", "fail"}:
                return False
        return None

    def _infer_success(self, result_data: Dict[str, Any]) -> bool:
        """
        Infer the success of the result data.
        """
        tl = self.to_bool(result_data.get("success"))
        if tl is not None:
            return tl
        alt = self.to_bool(result_data.get("agent_success"))
        if alt is not None:
            return alt
        # Scan steps from the end for explicit success markers
        steps = result_data.get("steps", [])
        for step in reversed(steps if isinstance(steps, list) else []):
            if not isinstance(step, dict):
                continue
            # Notte-style single action with success flag
            action = step.get("action")
            if isinstance(action, dict):
                act_success = self.to_bool(action.get("success"))
                if act_success is not None:
                    return act_success
            # Browser-use style: result array with success/is_done
            result_arr = step.get("result")
            if isinstance(result_arr, list):
                for r in reversed(result_arr):
                    if isinstance(r, dict):
                        r_success = self.to_bool(r.get("success"))
                        r_done = self.to_bool(r.get("is_done"))
                        if r_success is True or (r_done is True and r_success is not False):
                            return True
        return False

    async def evaluate_task(self, task_folder: Path) -> TaskResult | TaskError:
        """
        Evaluate a single task.
        """
        result = TaskResult()
        # Ensure aggregation keys are present
        result.task_id = task_folder.name

        data = self._load_result_file(task_folder)
        if not data:
            error = TaskError()
            error.task_id = task_folder.name
            error.error = "Result file not found or unreadable"
            error.error_type = "FileNotFoundError"
            error.error_message = "Result file not found or unreadable"
            return error

        task_field = data.get("task")
        result.task_description = (
            (task_field if isinstance(task_field, str) else None)
            or (task_field.get("task") if isinstance(task_field, dict) else None)
            or (task_field.get("description") if isinstance(task_field, dict) else None)
            or (task_field.get("prompt") if isinstance(task_field, dict) else None)
            or data.get("task_description")
            or data.get("prompt")
            or data.get("request")
            or "No task description"
        )

        history = self.extract_history(data)
        result.steps_count = len(history)

        screenshots = self.get_screenshots(task_folder)
        result.screenshots_count = len(screenshots)

        result.agent_results = self.extract_last_thinking(data)
        result.agent_error = data.get("error", "NA")

        # Prepare a compact, schema-agnostic last state snapshot (caps applied at string level)
        def _get_last_state(d: Dict[str, Any]) -> Dict[str, Any]:
            steps_any = d.get("steps")
            if isinstance(steps_any, list):
                for st in reversed(steps_any):
                    if isinstance(st, dict) and isinstance(st.get("state"), dict):
                        return st.get("state") or {}
            # Fallback: try from normalized history (current_state)
            if isinstance(history, list):
                for it in reversed(history):
                    if isinstance(it, dict):
                        mo = it.get("model_output")
                        cs = mo.get("current_state") if isinstance(mo, dict) else None
                        if isinstance(cs, dict):
                            return cs
            return {}

        last_state_obj = _get_last_state(data)
        try:
            last_state_json = json.dumps(last_state_obj, ensure_ascii=False)
        except Exception:  # pylint: disable=broad-exception-caught
            last_state_json = "{}"
        # Cap to avoid excessive prompt size
        if len(last_state_json) > 4000:
            last_state_json = last_state_json[:4000] + "...[cut]"

        import time
        start_time = time.monotonic()
        jr = await judge_with_retry(
            task=result.task_description,
            complete_history=history,
            final_result=(
                f"AGENT FINAL RESULTS:\n{data.get('results', 'No final results provided by agent')}\n\n"
                f"LAST STATE (JSON):\n{last_state_json}"
            ),
            last_message=f"Agent's Final Thinking: \
                {self.extract_last_thinking(data)}\n\nTask Context: \
                    {result.task_description}",
            screenshot_paths=screenshots,
            model=self.adapter,
            max_images=self.max_images,
        )
        elapsed = time.monotonic() - start_time

        # Log a concise evaluation summary (parity with legacy evaluator)
        logger.info("Evaluated %s: score=%d | summary=%s",
                    task_folder.name, jr.final_score, jr.task_summary)

        # Enrich result metadata
        # Prefer agent's model using legacy extraction logic; otherwise use judge model
        model_name = (
            data.get("model")
            or (data.get("task", {}).get("model") if isinstance(data.get("task"), dict) else None)
            or data.get("config", {}).get("model")
            or self.extract_agent_model(data)
            or self.adapter.model
            or "unknown"
        )
        result.model = str(model_name)
        result.latency = float(elapsed)
        # Prefer the agent's final output as agent_results
        try:
            result.agent_results = str(data.get('results', 'NA'))
        except Exception:  # pylint: disable=broad-exception-caught
            result.agent_results = "NA"
        # Capture token usage with preference for per-step agent-side usage
        tokens_list: list[Any] = []
        agent_tokens = data.get("tokens")
        if isinstance(agent_tokens, list):
            tokens_list.extend(agent_tokens)
        steps_any = data.get("steps")
        if isinstance(steps_any, list):
            for st in steps_any:
                if isinstance(st, dict):
                    st_tokens = st.get("tokens") or st.get("usage")
                    if st_tokens is not None:
                        tokens_list.append(st_tokens)
        usage = getattr(self.adapter, 'last_usage', None)
        if usage:
            tokens_list.append(usage)
            # Populate per-task judge-only usage summary
            if isinstance(usage, dict):
                if "prompt_tokens" in usage:  # OpenAI
                    pt = int(usage.get("prompt_tokens", 0) or 0)
                    ct = int(usage.get("completion_tokens", 0) or 0)
                    result.judge_token_usage = {
                        "prompt_tokens": pt,
                        "completion_tokens": ct,
                        "total_tokens": pt + ct,
                    }
                elif "prompt_token_count" in usage:  # Gemini
                    pt = int(usage.get("prompt_token_count", 0) or 0)
                    ct = int(usage.get("candidates_token_count", 0) or 0)
                    result.judge_token_usage = {
                        "prompt_tokens": pt,
                        "completion_tokens": ct,
                        "total_tokens": pt + ct,
                    }
        result.tokens = tokens_list

        # Post-processing: cap score if agent self-reported failure
        result.agent_success = self._infer_success(data)
        original_score = jr.final_score
        if not result.agent_success and original_score >= 70:
            capped_score = min(original_score, 69)
            jr.final_score = capped_score
            jr.reasoning = f"{jr.reasoning}\n\n[POST-PROCESSING NOTE: Score capped from \
                {original_score} to {capped_score} because agent self-reported failure. \
                    LLM cannot override agent's failure assessment.]"
        # Ensure enums are JSON-serializable and enrich fields
        result.evaluation = jr.model_dump()
        if isinstance(result.evaluation.get("error_categories"), list):
            result.evaluation["error_categories"] = [
                getattr(ec, "value", ec) for ec in result.evaluation["error_categories"]]

        # llm_success per spec: True only when final_score >= 70
        try:
            fs = result.evaluation.get('final_score', 0)
            result.llm_success = bool(fs >= 70)
        except Exception:  # pylint: disable=broad-exception-caught
            result.llm_success = False

        return result

    def extract_history(self, result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract the history from the result data.
        """
        history = result_data.get("complete_history")
        if isinstance(history, list) and history:
            first = history[0]
            if isinstance(first, dict) and ("model_output" in first or "result" in first):
                return history
        steps = result_data.get("steps", [])
        formatted: List[Dict[str, Any]] = []
        for i, step in enumerate(steps):
            state = step.get("state", {}) if isinstance(step, dict) else {}
            model_output = {
                "action": step.get("actions") or
                ([step.get("action")]
                 if step.get("action") else []),
                "current_state": {
                    "page_summary": state.get("page_summary", ""),
                    "memory": state.get("memory", ""),
                    "next_goal": state.get("next_goal", ""),
                    "url": state.get("url") or state.get("current_url") or state.get("page_url", ""),
                },
            }
            result_parts: List[Dict[str, Any]] = []
            for k in ("screenshot_path", "screenshot"):
                if isinstance(step, dict) and step.get(k):
                    result_parts.append({"screenshot_path": step[k]})
            formatted.append({"model_output": model_output,
                              "result": result_parts, "step_number": i + 1})
        return formatted

    def extract_last_thinking(self, result_data: Dict[str, Any]) -> str:
        """
        Extract the last thinking from the result data.
        """
        for key in ("complete_history", "steps"):
            arr = result_data.get(key)
            if isinstance(arr, list) and arr:
                for step in reversed(arr):
                    if not isinstance(step, dict):
                        continue
                    mo = step.get("model_output") or {}
                    if isinstance(mo, dict):
                        for k in ("thinking", "thought", "reasoning"):
                            v = mo.get(k)
                            if isinstance(v, str) and v.strip():
                                return v
                    for k in ("thinking", "thought", "reasoning"):
                        v2 = step.get(k)
                        if isinstance(v2, str) and v2.strip():
                            return v2
        return "No thinking available"

    def extract_agent_model(self, result_data: Dict[str, Any]) -> Optional[str]:
        """Best-effort extraction of the agent's model name used during the run."""
        for key in ("agent_model", "model", "llm_model", "provider_model"):
            val = result_data.get(key)
            if isinstance(val, str) and val.strip():
                return val
        req = result_data.get("request")
        if isinstance(req, dict):
            for key in ("model", "llm_model", "provider_model"):
                val = req.get(key)
                if isinstance(val, str) and val.strip():
                    return val
        steps = result_data.get("steps", [])
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                for key in ("model", "llm_model"):
                    val = step.get(key)
                    if isinstance(val, str) and val.strip():
                        return val
        return None

    @classmethod
    def from_cli(cls) -> "Evaluator":
        """
        Create an evaluator from the CLI.
        """
        parser = argparse.ArgumentParser(
            description="Evaluate web browsing agent results (standalone)")
        parser.add_argument("eval_folder", help="Path to evaluation folder")
        parser.add_argument("--model", default="gpt-4o")
        parser.add_argument("--max-images", type=int, default=10)
        parser.add_argument(
            "--output", help="Output file path (default: llm_judge.json in eval folder)")
        args = parser.parse_args()
        root = Path(args.eval_folder)
        if not root.exists():
            logger.error("Folder not found: %s", root)
            sys.exit(1)

        request = EvaluatorRequest(
            eval_folder=root,
            model=args.model,
            max_images=args.max_images,
            output=args.output,
            temperature=0.00)
        return cls(request)

    def scan_episodes(self, root: Path) -> List[Path]:
        """
        Scan the episodes from the root folder.
        """
        numbered = [p for p in root.iterdir() if p.is_dir()
                    and p.name.isdigit()]
        return sorted(numbered, key=lambda p: int(p.name)) if numbered else [root]

    def scan_tasks(self, ep: Path) -> List[Path]:
        """
        Scan the tasks from the episode folder.
        """
        return [p for p in ep.iterdir() if p.is_dir()
                and self.has_result_file(p)]

    async def run_tasks(self, tasks: List[Path]) -> List[Dict[str, Any]]:
        """
        Run the tasks.
        """
        results = []
        for p in tasks:
            logger.info("Starting task: %s", p.name)
            res = await self.evaluate_task(p)
            logger.info("Completed task: %s", p.name)
            results.append(res)
        return results


async def main():
    """
    Main function.
    """
    evaluator = Evaluator.from_cli()
    episodes = evaluator.scan_episodes(evaluator.eval_folder)

    results: List[Union[TaskResult, TaskError]] = []
    for ep in episodes:
        logger.info("Scanning episode: %s", ep)
        tasks = evaluator.scan_tasks(ep)
        logger.info("Found %d tasks", len(tasks))
        sema = asyncio.Semaphore(
            int(os.getenv("JUDGE_MAX_CONCURRENCY", str(JUDGE_MAX_CONCURRENCY))))

        async def _guarded(p: Path):
            async with sema:
                logger.info("Starting task: %s", p.name)
                try:
                    # Unset/empty env → no per-task timeout (matches README)
                    raw_to = os.getenv("JUDGE_TASK_TIMEOUT_SECONDS", "")
                    to_val = int(raw_to) if raw_to.strip() else 0
                    if to_val > 0:
                        res = await asyncio.wait_for(
                            evaluator.evaluate_task(p),
                            timeout=to_val)
                    else:
                        res = await evaluator.evaluate_task(p)
                    logger.info("Completed task: %s", p.name)
                    return res.model_dump() if isinstance(res, BaseModel) else res
                except asyncio.TimeoutError:
                    logger.error("Task timed out: %s", p.name)
                    return TaskError(task_id=p.name, error="timeout").model_dump()

        batch = await asyncio.gather(*[_guarded(p) for p in tasks], return_exceptions=False)
        results.extend(batch)

    # Legacy-style aggregation and output envelope
    all_evaluations: List[Dict[str, Any]] = []
    all_errors: List[Dict[str, Any]] = []
    episode_results: List[Dict[str, Any]] = []

    folder_type = "multi_episode" if len(
        episodes) > 1 or episodes[0] != evaluator.eval_folder else "single_episode"

    for ep in episodes:
        # Split per episode from the flat results by checking folder names present in tasks
        episode_tasks = [p for p in ep.iterdir() if p.is_dir()
                         and evaluator.has_result_file(p)]
        episode_ids = {p.name for p in episode_tasks}
        ep_items: List[Dict[str, Any]] = [r for r in results if r.get(
            "task_id") in episode_ids and not r.get("error")]
        ep_errs: List[Dict[str, Any]] = [r for r in results if r.get(
            "task_id") in episode_ids and r.get("error")]

        if ep_items:
            scores = [it["evaluation"]["final_score"] for it in ep_items]
            avg_score = sum(scores) / len(scores)
            llm_success_rate = len(
                [it for it in ep_items if it.get("llm_success")]) / len(ep_items)
            agent_success_rate = len([it for it in ep_items if it.get(
                "agent_success") is True]) / len(ep_items)
        else:
            avg_score = 0
            llm_success_rate = 0
            agent_success_rate = 0

        episode_results.append({
            "episode": ep.name,
            "total_tasks": len(episode_tasks),
            "evaluations_completed": len(ep_items),
            "evaluations_failed": len(ep_errs),
            "average_score": avg_score,
            "llm_success_rate": llm_success_rate,
            "agent_success_rate": agent_success_rate,
            "evaluations": ep_items,
            "errors": ep_errs,
        })

        all_evaluations.extend(ep_items)
        all_errors.extend(ep_errs)

    if all_evaluations:
        all_scores = [it["evaluation"]["final_score"]
                      for it in all_evaluations]
        overall_avg_score = sum(all_scores) / len(all_scores)
        overall_llm_success_rate = len(
            [it for it in all_evaluations if it.get("llm_success")]) / len(all_evaluations)
        overall_agent_success_rate = len([it for it in all_evaluations if it.get(
            "agent_success") is True]) / len(all_evaluations)
    else:
        overall_avg_score = 0
        overall_llm_success_rate = 0
        overall_agent_success_rate = 0

    # Compute judge-only token usage across all evaluations
    def _accumulate_usage(items: List[Dict[str, Any]]) -> Dict[str, int]:
        prompt_total = 0
        completion_total = 0
        for it in items:
            toks = it.get("tokens") or []
            u = toks[-1] if isinstance(toks, list) and toks and isinstance(toks[-1], dict) else None
            if not isinstance(u, dict):
                continue
            if "prompt_tokens" in u:  # OpenAI
                prompt_total += int(u.get("prompt_tokens", 0) or 0)
                completion_total += int(u.get("completion_tokens", 0) or 0)
            elif "prompt_token_count" in u:  # Gemini
                prompt_total += int(u.get("prompt_token_count", 0) or 0)
                completion_total += int(u.get("candidates_token_count", 0) or 0)
        return {
            "prompt_tokens": prompt_total,
            "completion_tokens": completion_total,
            "total_tokens": prompt_total + completion_total,
        }

    judge_token_usage = _accumulate_usage(all_evaluations)

    final_result = {
        "evaluation_folder": str(evaluator.eval_folder),
        "folder_type": folder_type,
        "total_episodes": len(episodes),
        "total_tasks": sum(er["total_tasks"] for er in episode_results),
        "evaluations_completed": sum(er["evaluations_completed"] for er in episode_results),
        "evaluations_failed": sum(er["evaluations_failed"] for er in episode_results),
        "overall_average_score": overall_avg_score,
        "overall_llm_success_rate": overall_llm_success_rate,
        "overall_agent_success_rate": overall_agent_success_rate,
        "episode_results": episode_results,
        "all_evaluations": all_evaluations,
        "all_errors": all_errors,
        "judge_token_usage": judge_token_usage,
    }

    output_file = Path(evaluator.output) if evaluator.output else (
        evaluator.eval_folder / JUDGE_RESULTS_FILE)
    output_file.write_text(json.dumps(
        final_result, indent=2), encoding="utf-8")
    logger.info("Saved: %s", output_file)


if __name__ == "__main__":
    asyncio.run(main())
