"""
Minimal GCS Aggregator Script

This script downloads all 'llm_judge.json' files from a series of GCS episode
folders, calculates the average 'agent_success_rate', and prints the result.

Usage:
    Set environment variables and run: python statistics.py

Environment Variables:
    - BASE_GCS_PATH: The base GCS path for episode data.
    - EPISODE_COUNT: The number of episodes to process.
    - JOB_NAME_TO_MONITOR: The job name for monitoring.
    - JOB_ID: The job ID for webhook notifications.
    - GCS_BUCKET_NAME: The name of the GCS bucket.
    - GCP_PROJECT_ID: The GCP project ID for authentication.
"""
import os
import sys
import logging

from pydantic import BaseModel

from neurosim.utils.webhook import Webhook
from neurosim.utils import StatusType
from neurosim.core.document import GFSUploader
from neurosim.core.storage import GCSUploader
from neurosim.utils.models import Metrics


class AggregatorRequest(BaseModel):
    """
    Aggregator request.
    """
    model_config = {"arbitrary_types_allowed": True}
    job_to_monitor: str
    save_path: str
    episode_count: int
    logger: logging.Logger


class Aggregator:
    """
    Aggregator class.

    Aggregates the GCS results and sends the success rate to the webhook.
    Also updates the Firestore document's status to COMPLETED.
    """

    def __init__(self, request: AggregatorRequest):
        """Initializes the Aggregator."""
        self.document = GFSUploader(request.job_to_monitor)
        self.logger = request.logger
        self.webhook = Webhook(request.logger)
        self.job_to_monitor = request.job_to_monitor
        self.save_path = request.save_path
        self.episode_count = request.episode_count
        self.uploader = GCSUploader()
        self.metrics = Metrics(
            id=self.job_to_monitor.replace("neurosim-", "").upper())

    def __update_status__(self, status: StatusType):
        """Updates the Firestore document's status to COMPLETED."""
        self.document.update({'status': status})
        self.webhook.send_status(self.job_to_monitor, status)
        self.logger.info(
            "🔥Updated Firestore document for %s to COMPLETED.", self.job_to_monitor)

    def __aggregate_gcs_results__(self):
        """Downloads JSONs, calculates comprehensive metrics across all episodes."""
        # Collect metrics from top-level keys (per episode)
        agent_success_rates = []
        llm_success_rates = []

        # Collect metrics from all_evaluations (per task/evaluation)
        all_steps = []
        all_total_tokens = []
        all_latencies = []

        # Track totals across all evaluations
        total_tokens_sum = 0
        total_input_tokens_sum = 0
        total_output_tokens_sum = 0

        for i in range(self.episode_count):
            gcs_file_path = f"{self.save_path}/{i}/llm_judge.json"
            self.logger.info(
                "Attempting to download: gs://%s/%s", self.uploader.bucket_name, gcs_file_path)
            self.logger.debug("BASE_GCS_PATH: %s, Episode: %d, Full path: %s",
                              self.save_path, i, gcs_file_path)

            try:
                data = self.uploader.download_json(gcs_file_path)

                # Extract top-level success rates
                agent_rate = data.get("overall_agent_success_rate")
                llm_rate = data.get("overall_llm_success_rate")

                if agent_rate is not None:
                    agent_success_rates.append(agent_rate)
                    self.logger.info(
                        "Found overall_agent_success_rate for episode %d: %f", i, agent_rate)
                else:
                    self.logger.warning(
                        "Key 'overall_agent_success_rate' not found in episode %d", i)

                if llm_rate is not None:
                    llm_success_rates.append(llm_rate)
                    self.logger.info(
                        "Found overall_llm_success_rate for episode %d: %f", i, llm_rate)
                else:
                    self.logger.warning(
                        "Key 'overall_llm_success_rate' not found in episode %d", i)

                # Extract evaluation-level metrics
                all_evaluations = data.get("all_evaluations", [])
                self.logger.info(
                    "Processing %d evaluations for episode %d", len(all_evaluations), i)

                for eval_data in all_evaluations:
                    # Extract steps_count
                    steps = eval_data.get("steps_count")
                    if steps is not None:
                        all_steps.append(steps)

                    # Extract and sum tokens from all token objects in the array
                    tokens_array = eval_data.get("tokens", [])
                    if tokens_array:
                        # Sum all tokens from all steps in this evaluation
                        evaluation_total_tokens = 0
                        evaluation_input_tokens = 0
                        evaluation_output_tokens = 0

                        for token_obj in tokens_array:
                            total_tokens = token_obj.get("total_tokens", 0)
                            prompt_tokens = token_obj.get("prompt_tokens", 0)
                            completion_tokens = token_obj.get(
                                "completion_tokens", 0)

                            evaluation_total_tokens += total_tokens
                            evaluation_input_tokens += prompt_tokens
                            evaluation_output_tokens += completion_tokens

                        if evaluation_total_tokens > 0:
                            all_total_tokens.append(evaluation_total_tokens)

                            # Add to grand totals
                            total_tokens_sum += evaluation_total_tokens
                            total_input_tokens_sum += evaluation_input_tokens
                            total_output_tokens_sum += evaluation_output_tokens

                    # Extract latency
                    latency = eval_data.get("latency")
                    if latency is not None:
                        all_latencies.append(latency)

            except FileNotFoundError:
                self.__update_status__(StatusType.FAILED)
                self.logger.warning(
                    "File not found, skipping episode %d: %s", i, gcs_file_path)
                continue
            except (ValueError, UnicodeDecodeError) as e:
                self.__update_status__(StatusType.FAILED)
                self.logger.error(
                    "Invalid JSON content in episode %d (%s): %s", i, gcs_file_path, str(e))
                continue
            except (OSError, RuntimeError) as e:
                self.__update_status__(StatusType.FAILED)
                self.logger.error(
                    "Network/GCS error processing episode %d (%s): %s", i, gcs_file_path, str(e))
                continue

        # Calculate averages
        avg_success_rate = sum(agent_success_rates) / \
            len(agent_success_rates) if agent_success_rates else 0
        avg_llm_judge_rate = sum(llm_success_rates) / \
            len(llm_success_rates) if llm_success_rates else 0
        avg_steps = sum(all_steps) / len(all_steps) if all_steps else 0
        avg_total_tokens = sum(all_total_tokens) / \
            len(all_total_tokens) if all_total_tokens else 0
        avg_time_taken = sum(all_latencies) / \
            len(all_latencies) if all_latencies else 0

        self.logger.info("Aggregation complete: %d episodes, %d evaluations processed",
                         len(agent_success_rates), len(all_steps))
        self.logger.info("Total tokens across all evaluations - Total: %d, Input: %d, Output: %d",
                         total_tokens_sum, total_input_tokens_sum, total_output_tokens_sum)

        # Update metrics object with all calculated values
        self.metrics.avg_success_rate = avg_success_rate
        self.metrics.avg_llm_judge_rate = avg_llm_judge_rate
        self.metrics.avg_total_tokens = avg_total_tokens
        self.metrics.avg_steps = avg_steps
        self.metrics.avg_time_taken = avg_time_taken
        self.metrics.total_tokens = total_tokens_sum
        self.metrics.total_input_tokens = total_input_tokens_sum
        self.metrics.total_output_tokens = total_output_tokens_sum

        # Send comprehensive results to webhook
        self.webhook.send_aggregated_results(self.metrics)

    def run(self):
        """Runs the Aggregator."""
        self.__aggregate_gcs_results__()
        self.__update_status__(StatusType.COMPLETED)

    @classmethod
    def from_env(cls) -> "Aggregator":
        """Initialize Aggregator from environment variables."""
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

        # Get required environment variables
        base_gcs_path = os.getenv("BASE_GCS_PATH")
        episode_count_str = os.getenv("EPISODE_COUNT")
        job_to_monitor = os.getenv("JOB_NAME_TO_MONITOR")

        # Validate required environment variables
        if not base_gcs_path:
            logger.error("BASE_GCS_PATH environment variable is not set")
            sys.exit(1)
        if not episode_count_str:
            logger.error("EPISODE_COUNT environment variable is not set")
            sys.exit(1)
        if not job_to_monitor:
            logger.error("JOB_NAME_TO_MONITOR environment variable is not set")
            sys.exit(1)

        # Parse episode count
        try:
            episode_count = int(episode_count_str)
        except ValueError:
            logger.error(
                "EPISODE_COUNT must be a valid integer, got: %s", episode_count_str)
            sys.exit(1)

        logger.info("Initializing aggregator with BASE_GCS_PATH=%s, EPISODE_COUNT=%d",
                    base_gcs_path, episode_count)

        request = AggregatorRequest(
            save_path=base_gcs_path,
            episode_count=episode_count,
            logger=logger,
            job_to_monitor=job_to_monitor,
        )
        return cls(request)


if __name__ == "__main__":
    aggregator = Aggregator.from_env()
    aggregator.run()
