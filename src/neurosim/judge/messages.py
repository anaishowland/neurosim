"""
Message classes for structured communication with LLM APIs.

This module provides standardized message structures for chat-based AI interactions,
supporting both text and image content in multimodal conversations.
"""

from typing import Any, List, Union


class ContentPartTextParam:
    """
    Represents a text content part for multimodal messages.

    Used to structure text content within messages that may contain
    both text and image elements.
    """

    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class ImageURL:
    """
    Container for image URL data.

    Simple wrapper class that holds a URL string for image content.
    Used as part of ContentPartImageParam for multimodal messages.
    """

    def __init__(self, url: str):
        self.url = url


class ContentPartImageParam:
    """
    Represents an image content part for multimodal messages.

    Used to structure image content within messages that may contain
    both text and image elements. Images are referenced by URL.
    """

    def __init__(self, image_url: ImageURL):
        self.type = "image_url"
        self.image_url = image_url


class BaseMessage:
    """
    Base class for all message types in chat conversations.

    Provides the fundamental structure for messages with a role (e.g., 'user', 'system')
    and content that can be either plain text or a list of mixed text/image parts.

    Args:
        role: The role of the message sender (e.g., 'user', 'system', 'assistant')
        content: Either a string or list of ContentPartTextParam/ContentPartImageParam objects
    """

    def __init__(self,
                 role: str,
                 content: Union[str, List[Union[ContentPartTextParam, ContentPartImageParam]]]):
        self.role = role
        self.content = content


class SystemMessage(BaseMessage):
    """
    System message for providing context and instructions to AI models.

    System messages typically contain instructions, context, or guidelines
    that inform the AI's behavior and responses.

    Args:
        content: The system message content (text or multimodal parts)
    """

    def __init__(self, content: Union[str, List[Any]]):
        super().__init__("system", content)


class UserMessage(BaseMessage):
    """
    User message representing input from the human user.

    User messages contain queries, requests, or other input from
    the human interacting with the AI system.

    Args:
        content: The user message content (text or multimodal parts)
    """

    def __init__(self, content: Union[str, List[Any]]):
        super().__init__("user", content)
