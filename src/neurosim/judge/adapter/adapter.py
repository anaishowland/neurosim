"""
Abstract base class for LLM adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict, Type, Union

from neurosim.judge.model.request import AdapterRequest
from neurosim.judge.model import OpenAIModel, GeminiModel


class Adapter(ABC):
    """
    Abstract base class for LLM adapters.
    """

    class CompletionWrapper:  # pylint: disable=too-few-public-methods
        """
        Internal wrapper class for LLM completion responses.

        This wrapper provides a consistent interface for handling completion objects
        from different LLM providers (OpenAI, Gemini, etc.) by storing the raw
        completion result in a standardized container.
        """

        def __init__(self, completion: Any):
            """
            Initialize the completion wrapper.

            Args:
                completion: The raw completion object or parsed model instance
            """
            self.completion = completion

    def __init__(self, request: AdapterRequest):
        """
        Initialize the adapter.
        """
        if request.model is None:
            raise ValueError("Model is not set")
        self.model: Union[OpenAIModel, GeminiModel] = request.model
        self.api_key = request.api_key
        self.temperature = request.temperature
        self.payload = None
        self.last_usage: Any | None = None

    @abstractmethod
    async def invoke(self,
                     messages: List[Any],
                     output_format: Optional[Type[Any]] = None) -> CompletionWrapper:
        """
        Invoke the model with the given messages.
        """
        self.payload = self._convert_browser_use_messages_to_openai(messages)
        raise NotImplementedError("Subclasses must implement this method.")

    @staticmethod
    def _convert_browser_use_messages_to_openai(messages: List[Any]) -> List[Dict[str, Any]]:
        """
        Convert browser-use message objects to OpenAI API format.

        This function transforms messages from the browser-use format (with custom message
        classes) into the dictionary format expected by OpenAI's API. It handles both
        text and image content parts, extracting role information and converting content
        structures appropriately.

        Args:
            messages: List of message objects with role and content attributes

        Returns:
            List of dictionaries in OpenAI API format with 'role' and 'content' keys
        """
        converted: List[Dict[str, Any]] = []
        for msg in messages:
            role = getattr(msg, "role", None) or msg.__class__.__name__.replace(
                "Message", "").lower()
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                parts: List[Dict[str, Any]] = []
                for part in content:
                    if getattr(part, "type", None) == "text" or \
                        (getattr(part, "__class__", None) and
                         part.__class__.__name__.endswith("TextParam")):
                        text = getattr(part, "text", None)
                        if text is not None:
                            parts.append({"type": "text", "text": text})
                    elif getattr(part, "type", None) == "image_url" or \
                            getattr(part, "__class__", None) and \
                            part.__class__.__name__.endswith("ImageParam"):
                        image_url_obj = getattr(part, "image_url", None)
                        url = getattr(image_url_obj, "url",
                                      None) if image_url_obj is not None else None
                        if url:
                            parts.append(
                                {"type": "image_url", "image_url": {"url": url}})
                converted.append({"role": role, "content": parts})
            else:
                converted.append({"role": role, "content": content})
        return converted
    __all__ = ["Adapter", "CompletionWrapper"]


__all__ = ["Adapter"]
