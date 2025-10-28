"""
Adapter for OpenAI API.
"""

from typing import List, Any, Optional, Type, Dict, cast, get_args
import copy
import json
import logging
import os

from openai import AsyncOpenAI

from neurosim.judge.adapter import Adapter
from neurosim.judge.model import AdapterRequest
from neurosim.judge.model import OpenAIModel

_JSON_SCHEMA_CACHE: Dict[type, Dict[str, Any]] = {}
log = logging.getLogger(__name__)


class OpenAIAdapter(Adapter):
    """
    Adapter for OpenAI API.
    """

    def __init__(self, request: AdapterRequest):
        if request.model is None:
            raise ValueError("Model is not set")
        # request.model is not OpenAIModel - raise ValueError
        if request.model not in get_args(OpenAIModel):
            raise ValueError("Model is not a OpenAI model")
        if request.api_key is None:
            request.api_key = os.getenv("OPENAI_API_KEY")
            if request.api_key is None:
                raise ValueError("OPENAI_API_KEY is not set")
        super().__init__(request)
        if request.temperature is None:
            raise ValueError("Temperature is not set")
        self.temperature = 1.0 if self.model.lower().startswith("gpt-5") else 0.0
        self.client = AsyncOpenAI(api_key=request.api_key)

    async def invoke(self, messages: List[Any],
                     output_format: Optional[Type[Any]] = None) -> Adapter.CompletionWrapper:
        """
        Invoke the OpenAI API with the given messages and optional structured output format.

        Args:
        messages: List of message objects to send to the API
        output_format: Optional Pydantic model class for structured JSON output.
                If provided, the response will be parsed and validated against this model.

        Returns:
            _CompletionWrapper: Wrapper containing either raw string content or 
            parsed model instance. Falls back to raw text if JSON parsing fails.

        Raises:
            OpenAI API exceptions may be propagated for network/auth issues
        """
        # Convert incoming message objects to OpenAI Chat Completions payload
        self.payload = self._convert_browser_use_messages_to_openai(messages)

        lower = self.model.lower()
        # Temperature defaults: 1.0 for gpt-5*, 0.0 otherwise
        temp: float
        if self.temperature is not None:
            temp = self.temperature
        elif lower.startswith("gpt-5"):
            temp = 1.0
        else:
            temp = 0.0

        log.info("OpenAI chat.completions.create model=%s temp=%f",
                 self.model, temp)
        response_format: Dict[str, Any] = {"type": "json_object"}
        # If a Pydantic model is provided, enforce strict JSON schema like the legacy wrapper

        def _set_no_additional_props(node: Any) -> Any:
            if isinstance(node, dict):
                node_type = node.get("type")
                if node_type == "object":
                    # Ensure root and nested objects explicitly disallow extra keys
                    node.setdefault("properties", {})
                    node["additionalProperties"] = False
                # Recurse into known child containers
                for key in list(node.keys()):
                    val = node[key]
                    if isinstance(val, (dict, list)):
                        _set_no_additional_props(val)
            elif isinstance(node, list):
                for item in node:
                    _set_no_additional_props(item)
            return node

        if output_format is not None and hasattr(output_format, "model_json_schema"):
            try:
                schema = _JSON_SCHEMA_CACHE.get(output_format)
                if schema is None:
                    # type: ignore[attr-defined]
                    schema = output_format.model_json_schema()
                    # Normalize for OpenAI: enforce additionalProperties: false on all objects
                    normalized = _set_no_additional_props(
                        copy.deepcopy(schema))
                    _JSON_SCHEMA_CACHE[output_format] = normalized
                    schema = normalized
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": getattr(output_format, "__name__", "JudgeResultSchema"),
                        "schema": schema,
                        "strict": True,
                    },
                }
            except (AttributeError, TypeError, ValueError) as e:
                log.warning(
                    "Failed to derive JSON schema from output model, \
                         falling back to json_object: %s", e)
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.warning(
                    "Unexpected error deriving JSON schema, falling back to json_object: %s", e)

        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, self.payload),
            temperature=temp,
            response_format=cast(Any, response_format),
            seed=42,
            timeout=120,
        )
        # Capture token usage if available
        try:
            usage = getattr(resp, 'usage', None)
            if usage is not None:
                self.last_usage = {
                    'prompt_tokens': getattr(usage, 'prompt_tokens', None),
                    'completion_tokens': getattr(usage, 'completion_tokens', None),
                    'total_tokens': getattr(usage, 'total_tokens', None),
                }
        except Exception:  # pylint: disable=broad-exception-caught
            self.last_usage = None
        content = resp.choices[0].message.content or ""

        if output_format is None:
            return Adapter.CompletionWrapper(content)
        try:
            parsed = json.loads(content)
            model_instance = output_format(**parsed)
            return Adapter.CompletionWrapper(model_instance)
        except json.JSONDecodeError as e:
            log.warning("Failed to decode JSON from model response: %s", e)
            return Adapter.CompletionWrapper(content)
        except (TypeError, ValueError) as e:
            log.warning(
                "Failed to instantiate output model from parsed JSON: %s", e)
            return Adapter.CompletionWrapper(content)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.warning("Unexpected error parsing model output: %s", e)
            return Adapter.CompletionWrapper(content)


__all__ = ["OpenAIAdapter"]
