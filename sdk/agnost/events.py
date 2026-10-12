"""
Event processing for Agnost Conversation SDK.

This module handles event processing in background threads.
"""

import logging
import threading
import time
from queue import Queue, Full
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("agnost.conversation.events")

FLUSH_TIMEOUT_SECONDS = 10.0


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
        while True:
            event_data = self._queue.get()
            try:
                if event_data is None:
                    return
                self._send_event(event_data)
            except Exception as e:
                logger.error(f"Worker error: {e}")
            finally:
                self._queue.task_done()

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

    def flush(self, timeout: float = FLUSH_TIMEOUT_SECONDS) -> bool:
        """Wait until all queued events have been sent."""
        logger.debug("Manual flush requested")
        deadline = time.monotonic() + timeout
        with self._queue.all_tasks_done:
            while self._queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning(f"flush() timed out with {self._queue.unfinished_tasks} events pending")
                    return False
                self._queue.all_tasks_done.wait(remaining)
        return True

    def shutdown(self) -> None:
        """Shutdown processor and flush remaining events."""
        logger.info("Shutting down EventProcessor")

        self.flush()
        self._shutdown_event.set()
        self._queue.put(None)

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

        self._session.close()
        logger.debug("EventProcessor shutdown complete")

    @property
    def queue_size(self) -> int:
        """Return current queue size."""
        return self._queue.qsize()
