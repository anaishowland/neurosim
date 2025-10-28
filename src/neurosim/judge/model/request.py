"""
Request for an adapter.
"""

from typing import Optional, Literal, Union
from pydantic import BaseModel


# Model aliases
OpenAIModel = Literal["gpt-5", "gpt-4o",
                      "gpt-4o-mini", "gpt-5-mini"]
GeminiModel = Literal["gemini-2.5-pro", "gemini-2.5-flash"]


class AdapterRequest(BaseModel):
    """
    Request for an adapter.
    """
    model: Optional[Union[OpenAIModel, GeminiModel]]
    api_key: Optional[str] = None
    temperature: Optional[float] = 0.00


__all__ = ["AdapterRequest", "OpenAIModel", "GeminiModel"]
