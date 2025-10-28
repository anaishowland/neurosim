"""Evaluation utilities.

This module defines the abstract :class:`Evaluation` type intended to be imported as:

    from neurosim.evaluation import Evaluation
"""

from __future__ import annotations

import argparse
import json
import os
import logging
import importlib.metadata
from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional
from dotenv import load_dotenv

from neurosim.core.storage import GCSUploader
from neurosim.utils.models import EvaluationConfig, EvaluationRequest, AgentResult, LLMType
from neurosim.constants import RESULT_FILE
from neurosim.utils.colored_formatter import ColoredFormatter

load_dotenv()


logger = logging.getLogger(__name__)


def _configure_logging_if_needed() -> None:
    """Install a sensible colored stream handler if no handlers exist.

    This avoids overriding application-level logging while ensuring
    examples and direct CLI runs produce logs by default.
    """
    root = logging.getLogger()
    if root.handlers:
        return
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)


class Evaluation(ABC):
    """Abstract base class for evaluation strategies.

    Subclasses must implement :meth:`evaluate`.
    """
    config: EvaluationConfig = EvaluationConfig(
        model="", tasks=[], save_path="")
    request: EvaluationRequest
    uploader: GCSUploader
    result: AgentResult
    _agent_name: Optional[str] = None
    _agent_commit_id: Optional[str] = None

    def __init__(self, request: EvaluationRequest) -> None:
        _configure_logging_if_needed()
        self.uploader = GCSUploader()
        self.request = request
        # Ensure config exists before use
        if not hasattr(self, "config") or self.config is None:
            self.config = EvaluationConfig(model="", tasks=[], save_path="")
        self.config.model = self.get_llm()
        self.config.save_path = os.path.join(
            self.request.userid,
            self.request.jobid,
            str(self.request.episode),
            self.request.taskid,
        )
        os.makedirs(self.config.save_path, exist_ok=True)
        self.result = AgentResult(
            jobId=self.request.jobid,
            task={"task": self.request.task,
                  "taskId": self.request.taskid, "model": self.config.model}
        )
        # Context-aware logger adapter for subclasses
        base_logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}")
        self.log = logging.LoggerAdapter(
            base_logger,
            {
                "jobId": self.request.jobid,
                "taskId": self.request.taskid,
                "userId": self.request.userid,
                "episode": self.request.episode,
                "model": self.request.model,
            },
        )
        # Best-effort context log (may be refined by subclasses)
        self.log.info("Evaluation initialized: %s",
                      self._describe_context())

    @property
    def agent_version(self) -> str:
        """Return the version of the agent."""
        if self._agent_name is None:
            raise ValueError("Agent name is not set")
        try:
            return importlib.metadata.version(self._agent_name.lower())
        except importlib.metadata.PackageNotFoundError:
            logger.warning("Agent version not found: %s", self._agent_name)
            return "unknown"

    @property
    def agent_name(self) -> str:
        """Return the name of the agent."""
        if self._agent_name is None:
            raise ValueError("Agent name is not set")
        return self._agent_name

    @agent_name.setter
    def agent_name(self, value: str) -> None:
        """Set the name of the agent."""
        self._agent_name = value

    @property
    def agent_commit_id(self) -> Optional[str]:
        """Return the commit id of the agent."""
        return self._agent_commit_id

    @agent_commit_id.setter
    def agent_commit_id(self, value: Optional[str]) -> None:
        """Set the commit id of the agent."""
        self._agent_commit_id = value

    def _describe_context(self) -> str:
        """Return a concise description of the evaluation context for logs."""
        user = getattr(self.request, "userid", "")
        jobid = getattr(self.request, "jobid", "")
        episode = getattr(self.request, "episode", "")
        taskid = getattr(self.request, "taskid", "")
        model = getattr(self.request, "model", "") or getattr(
            getattr(self, "config", object()), "model", "")
        return f"user={user}, jobId={jobid}, episode={episode}, taskId={taskid}, model={model}"

    @abstractmethod
    def get_llm(self) -> LLMType:
        """Retrieve the name of the language model to be used for evaluation."""
        raise NotImplementedError(
            "Subclasses must implement this method to return the LLM name.")

    async def execute(self):
        """
        Execute the task and return the results.
        """
        if self._agent_name is None:
            raise ValueError("Agent name is not set")
        if self._agent_commit_id is None:
            self.log.info("%s v%s", self._agent_name, self.agent_version)
        else:
            self.log.info("%s v%s %s", self._agent_name,
                          self.agent_version, self._agent_commit_id)
        try:
            response: AgentResult = await self.run()
            # Save structured JSON (not bytes); compression handled by uploader
            self.log.debug("Run completed: %s", self._describe_context())
            if response.error is None:
                self.compute_steps()
                self.log.info("Steps computed: %s", self._describe_context())
                # Note: subclasses define how screenshots/results are saved
                self.compute_tokens()
                self.log.info("Token computation completed: %s",
                              self._describe_context())
            self.save_results(response.model_dump())
        except Exception:  # noqa: BLE001  # pylint: disable=broad-except
            self.log.exception("Execution failed: %s",
                               self._describe_context())
            raise

    @abstractmethod
    async def run(self) -> AgentResult:
        """Run the evaluation process and return the results."""
        raise NotImplementedError(
            "Subclasses must implement this method to run the evaluation.")

    @abstractmethod
    def compute_steps(self) -> None:
        """Compute the number of steps required for the evaluation."""
        raise NotImplementedError(
            "Subclasses must implement this method to compute steps.")

    def save_screenshots(self, data: bytes, filename: str) -> None:
        """Save screenshots of the evaluation process to the specified path."""
        if not filename.endswith(".png"):
            raise ValueError("Only .png files are supported")
        blob_path = os.path.join(self.config.save_path, filename)
        self.log.debug("Uploading screenshot '%s' to %s", filename, blob_path)
        uri = self.uploader.upload_png(
            data=data,
            blob_path=blob_path,
            make_public=False)
        self.log.debug("Screenshot uploaded: %s", uri)

    def save_results(self, payload: Mapping[str, Any] | Any) -> None:
        """Save evaluation results to storage and log the resulting URI."""
        uri = self.uploader.upload_json(
            blob_path=os.path.join(self.config.save_path, RESULT_FILE),
            data=payload,
            make_public=False,
            compress_zstd=True,
            zstd_level=3,
        )
        self.log.debug("Results uploaded: %s", uri)

    @abstractmethod
    def compute_tokens(self) -> None:
        """Compute the number of tokens used during the evaluation."""
        raise NotImplementedError(
            "Subclasses must implement this method to compute tokens.")

    @classmethod
    def from_cli(cls) -> "Evaluation":
        """Create an Evaluation instance from command-line arguments.

        This method parses command-line arguments to construct an
        EvaluationRequest object, which is then used to instantiate
        an Evaluation object. It expects specific arguments to be
        provided via the command line, such as job ID, task details,
        user ID, and optional advanced settings.

        Returns:
            An instance of the Evaluation class initialized with
            parameters derived from the command-line input.
        """
        parser = argparse.ArgumentParser(
            description="Run BrowserAgent with given parameters.")
        parser.add_argument("--jobId", type=str,
                            required=True, help="Unique job ID")
        parser.add_argument("--task", type=str,
                            required=True, help="Task Description")
        parser.add_argument("--taskId", type=str,
                            required=True, help="Task ID")
        parser.add_argument("--browser", type=str, default="chrome",
                            required=False, help="Browser Channel - CHROME, MSEDGE, CHROMIUM")
        parser.add_argument("--episode", type=int,
                            required=True, help="Episode number")
        parser.add_argument("--user", type=str,
                            required=True, help="Unique user ID")
        parser.add_argument("--model", type=str, required=False,
                            default="gemini-2.5-flash-preview-05-20",
                            help="Model used to run the agent")
        parser.add_argument("--advanced_settings", type=json.loads,
                            required=False, default={}, help="Advanced config as JSON")

        args = parser.parse_args()

        # Fallbacks if optional args are missing
        advanced_settings = args.advanced_settings or {
            'episode': 0,
            'temperature': 0.00,
            'max_steps': 50,
            'max_action_per_step': 10,
            'max_retries': 3,
            'use_vision': True
        }

        request = EvaluationRequest(
            userid=args.user,
            model=args.model or '',
            jobid=args.jobId,
            task=args.task,
            taskid=args.taskId,
            browser_channel=args.browser,
            episode=int(os.getenv("CLOUD_RUN_TASK_INDEX", str(args.episode))),
            advanced_settings=advanced_settings,
            bucket_name=os.getenv("GCS_BUCKET_NAME", "")
        )
        logger.debug(
            "CLI request parsed: user=%s jobId=%s taskId=%s episode=%s model=%s browser=%s",
            request.userid,
            request.jobid,
            request.taskid,
            request.episode,
            request.model,
            request.browser_channel,
        )
        return cls(request)


__all__ = ["Evaluation"]
