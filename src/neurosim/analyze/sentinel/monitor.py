"""
Monitor the status of a given job
"""

import os
import sys
import logging
import time
from collections import Counter

import schedule
from google.cloud import run_v2
from google.api_core.exceptions import GoogleAPICallError

from neurosim.utils import MonitorRequest
from neurosim.core.document import GFSUploader
from neurosim.utils import Snapshot, StatusSummary, StatusType
from neurosim.utils.webhook import Webhook


class Monitor:
    """
    Monitor the status of a given job
    """

    def __init__(self, request: MonitorRequest):
        self.job_id = request.job_id
        self.task_count = request.total_tasks
        self.document = GFSUploader(request.job_id)
        self.run_client = run_v2.ExecutionsClient()
        self.job_path = self.get_job_path()
        self.snapshot = Snapshot(
            job_id=self.job_id,
            total_tasks=self.task_count,
            commit_id=request.commit_id,
            agent_version=request.agent_version
        )
        self.webhook = Webhook(logging.getLogger(__name__))
        self.previous_status = None  # Track previous status to avoid duplicate webhooks

    def get_job_path(self) -> str:
        """
            Cloud run path to the job executions.
        """
        project_id = os.getenv("GCP_PROJECT_ID")
        region = os.getenv("GCP_REGION")
        if not project_id or not region:
            raise ValueError("GCP_PROJECT_ID or GCP_REGION is not set")

        return f"projects/{project_id}/locations/{region}/jobs/{self.job_id}"

    def get_summary(self) -> bool:
        """
        Get a summary of a Cloud Run job's executions by status using the Python client library.
        Returns True if all tasks are completed (success + failed == total tasks), False otherwise.
        """
        try:
            execution_request = run_v2.ListExecutionsRequest(
                parent=self.job_path)
            executions = self.run_client.list_executions(
                request=execution_request)
            status_counts = Counter({
                StatusType.RUNNING: 0,
                StatusType.SUCCESS: 0,
                StatusType.FAILED: 0,
            })
            for execution in executions:
                state: StatusType = StatusType.UNKNOWN
                # The terminal condition is when 'Completed' condition is present.
                for cond in execution.conditions:
                    if cond.type_ == "Completed":
                        if cond.state == run_v2.Condition.State.CONDITION_SUCCEEDED:
                            state = StatusType.SUCCESS
                        elif cond.state == run_v2.Condition.State.CONDITION_FAILED:
                            state = StatusType.FAILED
                        else:  # Could be reconciling or another state
                            state = StatusType.RUNNING
                        break  # Found the final state

                # If not completed, check if it's running
                if state == StatusType.UNKNOWN and execution.running_count > 0:
                    state = StatusType.RUNNING

                status_counts[state] += 1
            if status_counts[StatusType.RUNNING] > 0:
                self.snapshot.status = StatusType.RUNNING
            self.snapshot.status_summary = StatusSummary(
                Success=status_counts[StatusType.SUCCESS],
                Failed=status_counts[StatusType.FAILED],
                Running=status_counts[StatusType.RUNNING]
            )
            logging.info("Status summary: %s", self.snapshot.status_summary)

            # Check if all tasks are completed
            success_count = self.snapshot.status_summary.get("Success", 0)
            failed_count = self.snapshot.status_summary.get("Failed", 0)
            completed_tasks = success_count + failed_count

            if completed_tasks == self.task_count:
                logging.info("All tasks completed! Success: %s, Failed: %s, Total: %s",
                             success_count, failed_count, self.task_count)
                return True

            logging.info("Tasks still running. Completed: %s/%s",
                         completed_tasks, self.task_count)
            # Only send webhook if status changed
            if self.previous_status != StatusType.RUNNING:
                self.webhook.send_status(self.job_id, StatusType.RUNNING)
                self.previous_status = StatusType.RUNNING
            return False

        except GoogleAPICallError as e:
            logging.error(
                "An unexpected error occurred while fetching job status: %s", e)
            # Only send webhook if status changed
            if self.previous_status != StatusType.FAILED:
                self.webhook.send_status(self.job_id, StatusType.FAILED)
                self.previous_status = StatusType.FAILED
            return False
        finally:
            self.update_snapshot()

    def update_snapshot(self):
        """
        Creates or updates a document in Firestore with the job's status.
        Determines job status (RUNNING, COMPLETED) based on summary.
        """
        self.document.update(self.snapshot.model_dump())

    def start_monitoring(self, interval_seconds: int = 30):
        """
        Start monitoring the job with periodic status checks.

        Args:
            interval_seconds: How often to check job status (default: 30 seconds)
        """
        # Run get_summary immediately on startup
        logging.info("Starting monitor for job: %s", self.job_id)
        if self.get_summary():
            logging.info("All tasks completed on startup - exiting")
            self.snapshot.status = StatusType.POST_PROCESS
            self.webhook.send_status(self.job_id, StatusType.POST_PROCESS)
            self.update_snapshot()
            return

        # Schedule get_summary to run at specified intervals
        schedule.every(interval_seconds).seconds.do(self.get_summary)
        logging.info(
            "Scheduled get_summary to run every %s seconds", interval_seconds)

        # Keep the scheduler running
        try:
            while True:
                schedule.run_pending()

                # Check if all tasks are completed after running scheduled jobs
                if self.snapshot.status_summary:
                    success_tasks = self.snapshot.status_summary.get(
                        "Success", 0)
                    failed_tasks = self.snapshot.status_summary.get(
                        "Failed", 0)
                    total_completed = success_tasks + failed_tasks

                    if total_completed == self.task_count:
                        logging.info("All tasks completed - stopping monitor")
                        self.snapshot.status = StatusType.POST_PROCESS
                        self.webhook.send_status(
                            self.job_id, StatusType.POST_PROCESS)
                        self.update_snapshot()
                        sys.exit(0)
                    elif failed_tasks == self.task_count:
                        logging.info("All tasks failed - stopping monitor")
                        self.snapshot.status = StatusType.FAILED
                        self.webhook.send_status(
                            self.job_id, StatusType.FAILED)
                        self.update_snapshot()
                        sys.exit(1)

                time.sleep(1)  # Small sleep to prevent high CPU usage
        except KeyboardInterrupt:
            logging.info("Monitor stopped by user")
            self.webhook.send_status(self.job_id, StatusType.CANCELLED)
        finally:
            self.update_snapshot()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    INTERVAL_SECONDS: int = 30

    # Check for required environment variables
    JOB_NAME_TO_MONITOR = os.getenv("JOB_NAME_TO_MONITOR")
    TOTAL_TASKS = os.getenv("TOTAL_TASKS")
    COMMIT_ID = os.getenv("COMMIT_ID")
    AGENT_VERSION = os.getenv("AGENT_VERSION")

    if not JOB_NAME_TO_MONITOR:
        logging.error("JOB_NAME_TO_MONITOR environment variable is not set")
        sys.exit(1)

    if not TOTAL_TASKS:
        logging.error("TOTAL_TASKS environment variable is not set")
        sys.exit(1)

    if not COMMIT_ID:
        logging.warning("COMMIT_ID environment variable is not set")

    if not AGENT_VERSION:
        logging.warning("AGENT_VERSION environment variable is not set")

    # Initialize and start the monitor
    monitor_request = MonitorRequest(
        job_id=JOB_NAME_TO_MONITOR,
        total_tasks=int(TOTAL_TASKS),
        commit_id=COMMIT_ID,
        agent_version=AGENT_VERSION
    )
    monitor = Monitor(monitor_request)

    # Start monitoring with 30-second intervals
    monitor.start_monitoring(INTERVAL_SECONDS)
