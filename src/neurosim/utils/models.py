"""Shared Pydantic models used across Neurosim.

This module defines lightweight data containers that are validated and
serializable. Import with:

    from neurosim.utils.models import AgentResult
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from enum import Enum

from typing import Any, Dict, List, Optional, TypeAlias
from typing_extensions import TypedDict

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveInt, NonNegativeInt

from google.cloud.firestore_v1.transforms import Sentinel
from google.cloud import firestore


class EvaluationConfig(BaseModel):
    """
    Configuration for evaluation settings.

    Attributes:
        model_config: Configuration dictionary allowing arbitrary types.
        model: The name or identifier of the model being evaluated.
        episode: The episode number, default is 2.
        temperature: The temperature setting for the evaluation, default is 0.00.
        tasks: A list of tasks, each represented as a dictionary with string keys and values.
        save_path: The file path where evaluation results will be saved.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    model: str
    episode: PositiveInt = 2
    temperature: NonNegativeFloat = 0.00
    tasks: List[Dict[str, str]]
    save_path: str


class EvaluationRequest(BaseModel):
    """
    Represents a request for an evaluation task.

    Attributes:
        userid: The unique identifier for the user making the request.
        model: The name or identifier of the model to be evaluated.
        jobid: The unique identifier for the evaluation job.
        task: The specific task to be evaluated.
        taskid: The unique identifier for the task.
        browser_channel: The communication channel used by the browser.
        episode: The episode number for the evaluation.
        advanced_settings: A dictionary containing advanced settings for the evaluation.
        bucket_name: The name of the bucket where results may be stored, 
                    defaults to the environment variable GCS_BUCKET_NAME.
    """
    userid: str
    model: str
    jobid: str
    task: str
    taskid: str
    browser_channel: str
    episode: int
    advanced_settings: Dict[str, Any]
    bucket_name: str = Field(
        default_factory=lambda: os.getenv("GCS_BUCKET_NAME", ""))


class AgentErrors(BaseModel):
    """
    Represents errors encountered by an agent during task execution.

    Attributes:
        name: The name of the error.
        traceback: The traceback information for the error.
        error: A description of the error.
    """

    name: str
    traceback: str
    error: str


class AgentResult(BaseModel):
    """
    Represents the result of an agent's task execution.

    Attributes:
        jobId: The unique identifier for the job associated with this result.
        success: A boolean indicating whether the task was successfully completed.
        latency: The time taken to complete the task, measured in seconds.
        tokens: A list of dictionaries representing token usage, with 
                string keys and integer values.
        task: A dictionary containing details of the task executed.
        steps: A list of dictionaries detailing each step taken during task execution.
        results: A string containing the results of the task execution.
        error: An optional AgentErrors object representing any errors 
                encountered during task execution.
    """
    jobId: str
    success: bool = False
    latency: NonNegativeFloat = 0.0
    tokens: List[Dict[str, int]] = Field(default_factory=list)
    task: Dict[str, Any] = Field(default_factory=dict)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    results: str = ''
    error: Optional[AgentErrors] = None

    def to_bytes(self) -> bytes:
        """Return UTF-8 encoded JSON bytes for this AgentResult."""
        return self.model_dump_json().encode('utf-8')


LLMType: TypeAlias = str | Any


class StatusType(str, Enum):
    """Status choices for Snapshot"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    QUEUED = "QUEUED"
    CANCELLED = "CANCELLED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    POST_PROCESS = "POST_PROCESS"
    COMPLETED = "COMPLETED"


class StatusSummary(TypedDict):
    """Status summary with specific allowed keys"""
    Success: NonNegativeInt
    Running: NonNegativeInt
    Failed: NonNegativeInt


class MonitorRequest(BaseModel):
    """
    Monitor request model
    """
    job_id: str
    total_tasks: int
    commit_id: Optional[str] = None
    agent_version: Optional[str] = None


class Snapshot(BaseModel):
    """
    Snapshot model
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    job_id: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    last_updated: Sentinel = Field(
        default_factory=lambda: firestore.SERVER_TIMESTAMP)
    total_tasks: NonNegativeInt
    status: StatusType = Field(default_factory=lambda: StatusType.QUEUED)
    status_summary: StatusSummary = Field(
        default_factory=lambda: {"Success": 0, "Running": 0, "Failed": 0})
    expire_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    commit_id: Optional[str] = None
    agent_version: Optional[str] = None


class Metrics(BaseModel):
    """
    Metrics model
    """
    id: str = Field(default_factory=lambda: "")
    avg_success_rate: NonNegativeFloat = Field(default_factory=lambda: 0.0)
    avg_llm_judge_rate: NonNegativeFloat = Field(default_factory=lambda: 0.0)
    avg_total_tokens: NonNegativeFloat = Field(default_factory=lambda: 0.0)
    avg_steps: NonNegativeFloat = Field(default_factory=lambda: 0.0)
    avg_time_taken: NonNegativeFloat = Field(default_factory=lambda: 0.0)
    total_tokens: NonNegativeInt = Field(default_factory=lambda: 0)
    total_input_tokens: NonNegativeInt = Field(default_factory=lambda: 0)
    total_output_tokens: NonNegativeInt = Field(default_factory=lambda: 0)


__all__ = ["EvaluationRequest", "EvaluationConfig",
           "AgentErrors", "AgentResult", "LLMType",
           "MonitorRequest", "Snapshot", "StatusType", "StatusSummary", "Metrics"]
