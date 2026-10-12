"""
Agnost Conversation SDK

A Python SDK for tracking AI conversations and events.

Example:
    import agnost

    # Initialize with your organization ID
    agnost.init("your-org-id")

    # Track an AI interaction
    agnost.track(
        user_id="user_123",
        input="What is the weather?",
        output="The weather is sunny.",
        agent_name="weather-agent"
    )

    # Identify a user
    agnost.identify("user_123", {
        "name": "John Doe",
        "email": "john@example.com",
        "plan": "paid"
    })

    # For partial events
    interaction = agnost.begin(
        user_id="user_123",
        agent_name="weather-agent"
    )
    interaction.set_input("Hello")
    interaction.end(output="Hi there!")

    # Ensure events are sent before exit
    agnost.shutdown()
"""

from .client import _client, ConversationClient
from .types import (
    ConversationConfig,
    Interaction,
    EventProperties,
    UserTraits,
    EventData,
    EventIOData,
    ConversationData,
)

__version__ = "0.1.0"
__all__ = [
    # Module-level functions (use the global client)
    "init",
    "track",
    "identify",
    "begin",
    "flush",
    "shutdown",
    "set_debug_logs",
    # Classes for direct instantiation
    "ConversationClient",
    "ConversationConfig",
    "Interaction",
    # Type aliases
    "EventProperties",
    "UserTraits",
    "EventData",
    "EventIOData",
    "ConversationData",
]


def init(write_key: str, config: ConversationConfig = None, **kwargs) -> bool:
    """
    Initialize the Agnost Conversation SDK.

    Args:
        write_key: Your Agnost organization ID
        config: Optional ConversationConfig instance
        **kwargs: Additional config options:
            - endpoint: API endpoint (default: "https://api.agnost.ai")
            - debug: Enable debug logging (default: False)

    Returns:
        bool: True if initialization was successful

    Example:
        import agnost

        # Basic initialization
        agnost.init("your-org-id")

        # With custom config
        agnost.init("your-org-id", endpoint="https://custom.endpoint.com", debug=True)
    """
    return _client.init(write_key, config, **kwargs)


def track(
    user_id: str = "",
    input: str = None,
    output: str = None,
    agent_name: str = "default",
    conversation_id: str = None,
    properties: dict = None,
    timestamp=None,
    success: bool = True,
    latency: int = None,
) -> str:
    """
    Track an AI interaction event.

    Args:
        user_id: User identifier (optional, defaults to empty string)
        input: Input text/prompt
        output: Output/response text
        agent_name: Agent name (default: "default")
        conversation_id: Conversation ID for grouping related events
        properties: Additional event properties
        timestamp: Event timestamp (defaults to now)
        success: Whether the interaction was successful
        latency: Execution time in milliseconds

    Returns:
        str: Event ID if queued successfully, None otherwise

    Example:
        event_id = agnost.track(
            user_id="user_123",
            input="What is the weather?",
            output="The weather is sunny.",
            agent_name="weather-agent",
            conversation_id="conv_abc",
            properties={"temperature": "0.7"},
            latency=1500
        )
    """
    return _client.track_ai(
        user_id=user_id,
        event="",
        input=input,
        output=output,
        agent_name=agent_name,
        conversation_id=conversation_id,
        properties=properties,
        timestamp=timestamp,
        success=success,
        latency=latency,
    )


def identify(user_id: str, traits: dict) -> bool:
    """
    Associate user characteristics with a user ID.

    Args:
        user_id: User identifier
        traits: User traits dictionary

    Returns:
        bool: True if identification was successful

    Example:
        agnost.identify("user_123", {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "plan": "paid"
        })
    """
    return _client.identify(user_id, traits)


def begin(
    user_id: str = "",
    agent_name: str = "default",
    input: str = None,
    conversation_id: str = None,
    properties: dict = None,
) -> Interaction:
    """
    Begin a partial interaction for deferred completion.

    Use this when you want to track input/output separately or when
    the output is not immediately available.

    Args:
        user_id: User identifier (optional, defaults to empty string)
        agent_name: Agent name (default: "default")
        input: Input text/prompt (optional, can also use set_input() later)
        conversation_id: Conversation ID
        properties: Initial properties

    Returns:
        Interaction: An interaction object to complete later

    Example:
        # Option 1: Pass input directly (recommended)
        interaction = agnost.begin(
            user_id="user_123",
            agent_name="weather-agent",
            input="What is the weather?"
        )
        # ... do async work ...
        interaction.end(output="The weather is sunny.")

        # Option 2: Set input later
        interaction = agnost.begin(
            user_id="user_123",
            agent_name="weather-agent"
        )
        interaction.set_input("What is the weather?")
        interaction.end(output="The weather is sunny.")
    """
    return _client.begin(
        user_id=user_id,
        event="",
        agent_name=agent_name,
        input=input,
        conversation_id=conversation_id,
        properties=properties,
    )


def flush() -> None:
    """
    Manually flush all queued events.

    Call this before your application exits if you want to ensure
    all events are sent.

    Example:
        agnost.flush()
    """
    _client.flush()


def shutdown() -> None:
    """
    Shutdown the SDK and flush remaining events.

    Call this when your application is shutting down to ensure
    all events are sent and resources are cleaned up.

    Example:
        agnost.shutdown()
    """
    _client.shutdown()


def set_debug_logs(enabled: bool) -> None:
    """
    Enable or disable debug logging.

    Args:
        enabled: True to enable debug logs, False to disable

    Example:
        agnost.set_debug_logs(True)  # See queued events
    """
    _client.set_debug_logs(enabled)
