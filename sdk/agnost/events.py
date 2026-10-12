"""
Event processing for Agnost Conversation SDK.

This module handles event processing in background threads.
"""

import logging
import threading
import time
from queue import Queue, Empty, Full
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("agnost.conversation.events")


class EventProcessor:
    """
    Handles event processing with background thread.

    Events are queued and sent in the background for optimal performance.
    """

    def __init__(self, endpoint: str, org_id: str):
        self.endpoint = endpoint
        self.org_id = org_id
        self._queue: Queue = Queue()
        self._session = requests.Session()
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        logger.debug("EventProcessor initialized")
        self._start_worker()

    def _start_worker(self) -> None:
        """Start background worker thread."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._shutdown_event.clear()
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()
            logger.debug("Background event worker started")

    def _worker_loop(self) -> None:
        """Background worker loop."""
        while not self._shutdown_event.is_set():
            try:
                event_data = self._queue.get(timeout=1.0)
                self._send_event(event_data)
                self._queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")

    def _send_event(self, event_data: Dict[str, Any]) -> None:
        """Send event to API."""
        try:
            response = self._session.post(
                f"{self.endpoint}/api/v1/capture-event",
                headers={
                    "Content-Type": "application/json",
                    "X-Org-Id": self.org_id,
                },
                json=event_data,
                timeout=10
            )
            response.raise_for_status()
            logger.debug(f"Event sent successfully: {event_data.get('event_id', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to send event: {e}")

    def queue_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Queue event for background processing.

        Args:
            event_data: Event data dictionary

        Returns:
            bool: True if queued successfully
        """
        try:
            self._queue.put(event_data, block=False)
            logger.debug(f"Event queued for processing")
            return True
        except Full:
            logger.warning("Event queue is full, dropping event")
            return False
        except Exception as e:
            logger.error(f"Failed to queue event: {e}")
            return False

    def flush(self) -> None:
        """Manually flush all queued events."""
        logger.debug("Manual flush requested")

        # Process all queued events
        while True:
            try:
                event_data = self._queue.get_nowait()
                self._send_event(event_data)
                self._queue.task_done()
            except Empty:
                break

    def shutdown(self) -> None:
        """Shutdown processor and flush remaining events."""
        logger.info("Shutting down EventProcessor")

        # Flush remaining events
        self.flush()

        # Signal shutdown
        self._shutdown_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

        self._session.close()
        logger.debug("EventProcessor shutdown complete")

    @property
    def queue_size(self) -> int:
        """Return current queue size."""
        return self._queue.qsize()
