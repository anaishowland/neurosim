"""Webhook utilities"""

import logging
import os
from typing import Optional
from pydantic import BaseModel
import requests
from neurosim.utils.models import StatusType
from neurosim.utils.models import Metrics


class WebhookPayload(BaseModel):
    """Webhook payload"""
    type: str
    payload: dict


class Webhook:
    """Webhook class"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.webhook_url: Optional[str] = os.getenv("WEBHOOK_URL")
        if not self.webhook_url:
            self.logger.warning("WEBHOOK_URL not set. Skipping webhook.")

    def __send__(self, payload: WebhookPayload):
        """Sends a webhook."""
        if not self.webhook_url:
            self.logger.warning("WEBHOOK_URL not set. Skipping webhook.")
            return
        try:
            resp = requests.post(
                self.webhook_url, json=payload.model_dump(), timeout=10)
            resp.raise_for_status()
            self.logger.info(
                f"✅ Webhook sent for {payload.payload['id']} with {payload.type}.")
        except requests.RequestException as e:
            self.logger.error(f"❌ Failed to send {payload.type} webhook: {e}")

    def send_status(self, job_id: str, status: StatusType):
        """Sends a job status update to the webhook."""
        if not self.webhook_url:
            self.logger.warning("WEBHOOK_URL not set. Skipping webhook.")
            return
        # Format job_id: remove "neurosim-" prefix and convert to uppercase
        formatted_job_id = job_id.replace("neurosim-", "").upper()
        payload = WebhookPayload(
            type="job_status",
            payload={
                "id": formatted_job_id,
                "status": status.value
            }
        )
        self.__send__(payload)

    def send_success_rate(self, job_id: str, success_rate: float):
        """Sends the final success rate to the webhook."""
        if not self.webhook_url:
            self.logger.warning("WEBHOOK_URL not set. Skipping webhook.")
        # Format job_id: remove "neurosim-" prefix and convert to uppercase
        formatted_job_id = job_id.replace("neurosim-", "").upper()
        payload = WebhookPayload(
            type="success_rate",
            payload={
                "id": formatted_job_id,
                "avg_success_rate": str(success_rate)
            }
        )
        self.__send__(payload)

    def send_aggregated_results(self, metrics: Metrics):
        """Sends comprehensive aggregated results to the webhook."""
        if not self.webhook_url:
            self.logger.warning("WEBHOOK_URL not set. Skipping webhook.")

        payload = WebhookPayload(
            type="aggregated_results",
            payload=metrics.model_dump()
        )
        self.__send__(payload)
