"""
Agnost Conversation SDK Client.

This module provides the main client for tracking AI conversations and events.
"""

import json
import uuid
import logging
import atexit
from typing import Any, Optional, Dict
from datetime import datetime

import requests

from .types import (
    ConversationConfig,
    Interaction,
    EventProperties,
    UserTraits,
)
from .events import EventProcessor
from .session import SessionManager

logger = logging.getLogger("agnost.conversation")


class ConversationClient:
    """
    Client for tracking AI conversations and events.

    This client provides methods to track AI interactions, manage conversations,
    and identify users.

    Example:
        import agnost_conversation as agnost

        agnost.init("your-org-id")

        agnost.track(
            user_id="user_123",
            input="What is the weather?",
            output="The weather is sunny.",
            agent_name="weather-agent"
        )
    """

    def __init__(self):
        self._initialized = False
        self._write_key: Optional[str] = None
        self._config: Optional[ConversationConfig] = None
        self._event_processor: Optional[EventProcessor] = None
        self._session_manager: Optional[SessionManager] = None
        self._http_session: Optional[requests.Session] = None

    def init(
        self,
        write_key: str,
        config: Optional[ConversationConfig] = None,
        **kwargs
    ) -> bool:
        """
        Initialize the SDK with your organization ID.

        Args:
            write_key: Your Agnost organization ID
            config: Optional ConversationConfig instance
            **kwargs: Additional config options (endpoint, debug)

        Returns:
            bool: True if initialization was successful
        """
        if self._initialized:
            logger.debug("SDK already initialized")
            return True

        try:
            self._write_key = write_key

            # Build config from kwargs or use provided config
            if config:
                self._config = config
            else:
                self._config = ConversationConfig(**kwargs)

            # Set up logging
            if self._config.debug:
                logging.getLogger("agnost.conversation").setLevel(logging.DEBUG)
                logging.getLogger("agnost.conversation.events").setLevel(logging.DEBUG)
                logging.getLogger("agnost.conversation.session").setLevel(logging.DEBUG)

            logger.info(f"Initializing Agnost Conversation SDK - Endpoint: {self._config.endpoint}")

            # Initialize HTTP session
            self._http_session = requests.Session()

            # Initialize components
            self._event_processor = EventProcessor(
                self._config.endpoint,
                write_key
            )

            self._session_manager = SessionManager(
                self._config.endpoint,
                write_key,
                self._config,
                self._http_session
            )

            # Register shutdown handler
            atexit.register(self._shutdown_handler)

            self._initialized = True
            logger.info("Agnost Conversation SDK initialized successfully")
            return True

        except Exception as e:
            logger.error(f"SDK initialization failed: {e}")
            return False

    def _shutdown_handler(self):
        """Atexit handler for clean shutdown."""
        self.shutdown()

    def track_ai(
        self,
        user_id: str,
        event: str = "",
        input: Optional[str] = None,
        output: Optional[str] = None,
        agent_name: str = "default",
        conversation_id: Optional[str] = None,
        properties: Optional[EventProperties] = None,
        timestamp: Optional[datetime] = None,
        success: bool = True,
        latency: Optional[int] = None,
    ) -> Optional[str]:
        """
        Track an AI interaction event.

        Args:
            user_id: User identifier (optional, defaults to empty string)
            event: Event name (defaults to empty string)
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
        """
        if not self._initialized:
            logger.warning("SDK not initialized. Call init() first.")
            return None

        try:
            event_id = str(uuid.uuid4())
            ts = timestamp or datetime.utcnow()

            # Ensure conversation exists
            session_id = self._session_manager.get_or_create_conversation(
                conversation_id, user_id
            )

            # Build event metadata
            event_metadata = {}
            if properties:
                for k, v in properties.items():
                    event_metadata[str(k)] = str(v)
            event_metadata["event_type"] = event

            # Build event data
            event_data = {
                "event_id": event_id,
                "session_id": session_id,
                "primitive_type": event,
                "primitive_name": agent_name or event,
                "latency": latency or 0,
                "success": success,
                "args": "" if input is None else json.dumps(input),
                "result": "" if output is None else json.dumps(output),
                "metadata": event_metadata,
            }

            # Queue for processing
            if self._event_processor.queue_event(event_data):
                logger.debug(f"Event tracked: {event_id} - {event}")
                return event_id
            else:
                logger.warning("Failed to queue event")
                return None

        except Exception as e:
            logger.error(f"Failed to track event: {e}")
            return None

    def identify(self, user_id: str, traits: UserTraits) -> bool:
        """
        Associate user characteristics with a user ID.

        Args:
            user_id: User identifier
            traits: User traits dictionary (e.g., name, email, plan)

        Returns:
            bool: True if identification was successful

        Example:
            agnost.identify("user_123", {
                "name": "John Doe",
                "email": "john@example.com",
                "plan": "paid"
            })
        """
        if not self._initialized:
            logger.warning("SDK not initialized. Call init() first.")
            return False

        if not user_id:
            logger.warning("user_id is required")
            return False

        return self._session_manager.identify_user(user_id, traits)

    def begin(
        self,
        user_id: str,
        event: str = "",
        agent_name: str = "default",
        input: Optional[str] = None,
        conversation_id: Optional[str] = None,
        properties: Optional[EventProperties] = None,
    ) -> Optional[Interaction]:
        """
        Begin a partial interaction for deferred completion.

        Use this when you want to track input/output separately or when
        the output is not immediately available.

        Args:
            user_id: User identifier (optional, defaults to empty string)
            event: Event name (defaults to empty string)
            agent_name: Agent name (default: "default")
            input: Input text/prompt (optional, can also use set_input() later)
            conversation_id: Conversation ID
            properties: Initial properties

        Returns:
            Interaction: An interaction object to complete later

        Example:
            # Option 1: Pass input directly
            interaction = agnost.begin(
                user_id="user_123",
                agent_name="weather-agent",
                input="What is the weather?"
            )
            # ... process request ...
            interaction.end(output="The weather is sunny.")

            # Option 2: Set input later
            interaction = agnost.begin(
                user_id="user_123",
                agent_name="weather-agent"
            )
            interaction.set_input("What is the weather?")
            interaction.end(output="The weather is sunny.")
        """
        if not self._initialized:
            logger.warning("SDK not initialized. Call init() first.")
            return None

        event_id = str(uuid.uuid4())

        # Ensure conversation exists
        if conversation_id:
            self._session_manager.get_or_create_conversation(conversation_id, user_id)

        return Interaction(
            event_id=event_id,
            user_id=user_id,
            event=event,
            conversation_id=conversation_id,
            agent_name=agent_name,
            input=input,
            properties=properties,
            _send_callback=self._send_interaction
        )

    def _send_interaction(
        self,
        event_id: str,
        user_id: str,
        event: str,
        input: Optional[str],
        output: Optional[str],
        agent_name: str,
        conversation_id: Optional[str],
        properties: Optional[EventProperties],
        success: bool,
        latency: Optional[int]
    ) -> None:
        """Internal callback for sending completed interactions."""
        self.track_ai(
            user_id=user_id,
            event=event,
            input=input,
            output=output,
            agent_name=agent_name,
            conversation_id=conversation_id,
            properties=properties,
            success=success,
            latency=latency
        )

    def flush(self) -> None:
        """
        Manually flush all queued events.

        Call this before your application exits if you want to ensure
        all events are sent.
        """
        if not self._initialized:
            logger.warning("SDK not initialized")
            return

        logger.debug("Flushing events")
        if self._event_processor:
            self._event_processor.flush()

    def shutdown(self) -> None:
        """
        Shutdown the SDK and flush remaining events.

        Call this when your application is shutting down to ensure
        all events are sent and resources are cleaned up.
        """
        if not self._initialized:
            return

        logger.info("Shutting down Agnost Conversation SDK")

        if self._event_processor:
            self._event_processor.shutdown()

        if self._session_manager:
            self._session_manager.shutdown()

        if self._http_session:
            self._http_session.close()

        self._initialized = False
        logger.debug("SDK shutdown complete")

    def set_debug_logs(self, enabled: bool) -> None:
        """
        Enable or disable debug logging.

        Args:
            enabled: True to enable debug logs, False to disable
        """
        level = logging.DEBUG if enabled else logging.INFO
        logging.getLogger("agnost.conversation").setLevel(level)
        logging.getLogger("agnost.conversation.events").setLevel(level)
        logging.getLogger("agnost.conversation.session").setLevel(level)
        logger.debug(f"Debug logging {'enabled' if enabled else 'disabled'}")

    @property
    def is_initialized(self) -> bool:
        """Check if SDK is initialized."""
        return self._initialized

    @property
    def queue_size(self) -> int:
        """Get current event queue size."""
        if self._event_processor:
            return self._event_processor.queue_size
        return 0


# Global client instance
_client = ConversationClient()
