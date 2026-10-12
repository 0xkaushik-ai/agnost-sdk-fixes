"""
Type definitions for Agnost Conversation SDK.

This module defines types for configuration, events, conversations, and interactions.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import time


# Type aliases
UserTraits = Dict[str, Any]
EventProperties = Dict[str, Any]
EventMetadata = Dict[str, str]


@dataclass
class ConversationConfig:
    """Configuration for Agnost Conversation SDK."""

    endpoint: str = "https://api.agnost.ai"
    debug: bool = False

    def __post_init__(self):
        self.endpoint = self.endpoint.rstrip('/')


@dataclass
class EventData:
    """Internal representation of an event."""

    id: str
    org_id: str
    conversation_id: str
    timestamp: datetime
    success: bool = True
    io_id: Optional[str] = None
    latency: int = 0
    user_id: str = ""
    agent_name: str = ""
    event_metadata: EventMetadata = field(default_factory=dict)


@dataclass
class EventIOData:
    """Internal representation of event input/output."""

    id: str
    input: str = ""
    output: str = ""


@dataclass
class ConversationData:
    """Internal representation of a conversation."""

    id: str
    org_id: str
    created_at: datetime
    last_message_at: datetime
    user_id: str = ""
    user_metadata: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)


class Interaction:
    """
    Represents an in-progress AI interaction.

    Use this to track events that span multiple steps or have deferred outputs.

    Example:
        interaction = agnost.begin(
            user_id="user_123",
            agent_name="my-agent"
        )
        interaction.set_input("What is the weather?")
        # ... do work ...
        interaction.end(output="The weather is sunny.")
    """

    def __init__(
        self,
        event_id: str,
        user_id: str = "",
        event: str = "",
        conversation_id: Optional[str] = None,
        agent_name: str = "default",
        input: Optional[str] = None,
        properties: Optional[EventProperties] = None,
        _send_callback = None
    ):
        self.event_id = event_id
        self.user_id = user_id
        self.event = event
        self.conversation_id = conversation_id
        self.agent_name = agent_name
        self.properties = properties or {}
        self._input: Optional[str] = input
        self._output: Optional[str] = None
        self._finished = False
        self._send_callback = _send_callback
        self._start_time = time.time() 

    def set_input(self, text: str) -> "Interaction":
        """Set the input text for this interaction."""
        if self._finished:
            raise RuntimeError("Cannot modify a finished interaction")
        self._input = text
        return self

    def set_properties(self, properties: EventProperties) -> "Interaction":
        """Set or update properties for this interaction."""
        if self._finished:
            raise RuntimeError("Cannot modify a finished interaction")
        self.properties.update(properties)
        return self

    def set_property(self, key: str, value: Any) -> "Interaction":
        """Set a single property for this interaction."""
        if self._finished:
            raise RuntimeError("Cannot modify a finished interaction")
        self.properties[key] = value
        return self

    def end(
        self,
        output: Optional[str] = None,
        success: bool = True,
        latency: Optional[int] = None,
        **extra
    ) -> str:
        """
        Complete the interaction and send the event.

        Args:
            output: The output/result of the interaction
            success: Whether the interaction was successful
            latency: Execution time in milliseconds (optional, auto-calculated if not provided)
            **extra: Additional properties to merge

        Returns:
            str: The event ID
        """
        if self._finished:
            raise RuntimeError("Interaction already finished")

        # Auto-calculate latency if not provided
        if latency is None:
            elapsed_seconds = time.time() - self._start_time
            latency = int(elapsed_seconds * 1000)  # Convert to milliseconds

        self._output = output
        self._finished = True

        if extra:
            self.properties.update(extra)

        self._send_callback(
            event_id=self.event_id,
            user_id=self.user_id,
            event=self.event,
            input=self._input,
            output=output,
            agent_name=self.agent_name,
            conversation_id=self.conversation_id,
            properties=self.properties,
            success=success,
            latency=latency
        )

        return self.event_id

    def finish(
        self,
        output: Optional[str] = None,
        success: bool = True,
        latency: Optional[int] = None,
        **extra
    ) -> str:
        """
        Deprecated: Use end() instead.

        Complete the interaction and send the event.

        Args:
            output: The output/result of the interaction
            success: Whether the interaction was successful
            latency: Execution time in milliseconds (optional, auto-calculated if not provided)
            **extra: Additional properties to merge

        Returns:
            str: The event ID
        """
        return self.end(output=output, success=success, latency=latency, **extra)
