"""
Adapter for Gemini models.
"""

from typing import List, Any, Optional, Type, get_args
import io
import base64
import json
import asyncio

from PIL import Image as PILImage
from google import genai

from neurosim.judge.adapter import Adapter
from neurosim.judge.model import AdapterRequest
from neurosim.judge.model import GeminiModel


class GeminiAdapter(Adapter):
    """
    Adapter for Gemini models.
    """

    def __init__(self, request: AdapterRequest):
        """
        Initialize the Gemini adapter.
        """
        if request.model is None:
            raise ValueError("Model is not set")
        # request.model is not GeminiModel - raise ValueError
        if request.model not in get_args(GeminiModel):
            raise ValueError("Model is not a Gemini model")
        super().__init__(request)
        self._genai = genai.Client(
            vertexai=True, project='evaluation-deployment', location='us-central1')

    async def invoke(self, messages: List[Any], output_format: Optional[Type[Any]] = None) -> Adapter.CompletionWrapper:
        """
        Invoke the Gemini API with the given messages and optional structured output format.

        This method converts messages to Gemini's expected format, handling:
        - System messages are prefixed with "System: " text
        - Multimodal content including text and base64 encoded images
        - Image conversion from base64 data URLs to PIL Image objects
        - Asynchronous execution using thread-based delegation

        Args:
                messages: List of message objects to send to the API
                output_format: Optional Pydantic model class for structured JSON output.
                    If provided, the response will be parsed and validated against this model.

        Returns:
                CompletionWrapper: Wrapper containing either 
                raw string content or parsed model instance. 
                Falls back to raw text if JSON parsing fails.

        Note:
                Unlike OpenAIAdapter, this implementation uses basic exception handling 
                for JSON parsing without detailed error logging or multiple exception types.
        """
        # Convert incoming message objects to OpenAI-style payload first, then map
        self.payload = self._convert_browser_use_messages_to_openai(messages)
        gemini_input: List[Any] = []
        for m in self.payload:
            if m["role"] == "system":
                gemini_input.append(
                    f"System: {m['content'] if isinstance(m['content'], str) else ''}")
            elif m["role"] == "user":
                content = m["content"]
                if isinstance(content, list):
                    for part in content:
                        if part.get("type") == "text":
                            gemini_input.append(part["text"])
                        elif part.get("type") == "image_url":
                            url = part["image_url"]["url"]
                            if isinstance(url, str) and url.startswith("data:image"):
                                b64 = url.split(",", 1)[1]
                                img = PILImage.open(
                                    io.BytesIO(base64.b64decode(b64)))
                                gemini_input.append(img)
                else:
                    gemini_input.append(content)

        def _call_sync():
            return self._genai.models.generate_content(self.model, gemini_input)

        response = await asyncio.to_thread(_call_sync)
        text = getattr(response, "text", "") or ""
        # Capture pseudo-usage if counts exposed (genai may not provide usage)
        try:
            usage = getattr(response, 'usage_metadata', None)
            if usage is not None:
                self.last_usage = {
                    'prompt_tokens': getattr(usage, 'prompt_token_count', None),
                    'completion_tokens': getattr(usage, 'candidates_token_count', None),
                    'total_tokens': getattr(usage, 'total_token_count', None),
                }
        except Exception:  # pylint: disable=broad-exception-caught
            self.last_usage = None
        if output_format is None:
            return Adapter.CompletionWrapper(text)
        try:
            parsed = json.loads(text)
            model_instance = output_format(**parsed)
            return Adapter.CompletionWrapper(model_instance)
        except Exception:  # pylint: disable=broad-exception-caught
            return Adapter.CompletionWrapper(text)


__all__ = ["GeminiAdapter"]
