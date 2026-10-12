"""
Session/Conversation management for Agnost Conversation SDK.

This module handles conversation sessions and user identification.
"""

import uuid
import logging
from typing import Any, Callable, Dict, Optional
from datetime import datetime

import requests

from .types import ConversationConfig, UserTraits

logger = logging.getLogger("agnost.conversation.session")


class SessionManager:
    """Manages conversation sessions and user identification."""

    def __init__(
        self,
        endpoint: str,
        org_id: str,
        config: ConversationConfig,
        http_session: Optional[requests.Session] = None,
        queue_session: Optional[Callable[[Dict[str, Any]], bool]] = None
    ):
        self.endpoint = endpoint
        self.org_id = org_id
        self.config = config
        self._session = http_session or requests.Session()
        self._queue_session = queue_session
        self._conversations: Dict[str, str] = {}  # conversation_id -> session_id mapping
        self._user_traits: Dict[str, UserTraits] = {}  # user_id -> traits mapping
        logger.debug(f"SessionManager initialized for org: {org_id}")

    def get_or_create_conversation(
        self,
        conversation_id: Optional[str],
        user_id: str,
        user_traits: Optional[UserTraits] = None
    ) -> str:
        """
        Get existing conversation or create new one.

        Args:
            conversation_id: Optional conversation ID. If None, generates new one.
            user_id: User identifier
            user_traits: Optional user traits/metadata

        Returns:
            str: Conversation/session ID
        """
        # Generate conversation_id if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            logger.debug(f"Generated new conversation ID: {conversation_id}")

        # Check if we already have this conversation
        if conversation_id in self._conversations:
            logger.debug(f"Using existing conversation: {conversation_id}")
            return conversation_id

        # Create new conversation session
        logger.debug(f"Creating new conversation for user: {user_id}")
        return self._create_conversation(conversation_id, user_id, user_traits)

    def _create_conversation(
        self,
        conversation_id: str,
        user_id: str,
        user_traits: Optional[UserTraits] = None
    ) -> str:
        """Create a new conversation session."""
        try:
            # Merge stored traits with provided traits
            merged_traits = {}
            if user_id in self._user_traits:
                merged_traits.update(self._user_traits[user_id])
            if user_traits:
                merged_traits.update(user_traits)

            # Build user_data dict
            user_data = {"user_id": user_id}
            if merged_traits:
                user_data.update(merged_traits)

            session_payload = {
                "session_id": conversation_id,
                "client_config": "conversation_sdk",
                "connection_type": "sdk",
                "ip": "",
                "user_data": user_data,
            }

            if not self._queue_session(session_payload):
                logger.error(f"Failed to queue conversation: {conversation_id}")
                return conversation_id
            self._conversations[conversation_id] = conversation_id
            logger.debug(f"New conversation queued: {conversation_id} for user: {user_id}")
            return conversation_id

        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            return conversation_id

    def identify_user(self, user_id: str, traits: UserTraits) -> bool:
        """
        Store user traits for identification.

        Args:
            user_id: User identifier
            traits: User traits dictionary

        Returns:
            bool: True if stored successfully
        """
        try:
            self._user_traits[user_id] = traits
            logger.debug(f"User identified: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to identify user: {e}")
            return False

    def get_user_traits(self, user_id: str) -> Optional[UserTraits]:
        """Get stored traits for a user."""
        return self._user_traits.get(user_id)

    def shutdown(self) -> None:
        """Clean up resources."""
        self._session.close()
        logger.debug("SessionManager shutdown complete")
