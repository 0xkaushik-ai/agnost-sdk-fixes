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
MAX_QUEUE_SIZE = 10000
MAX_ATTEMPTS = 3


class EventProcessor:
    """
    Handles event processing with background thread.

    Events are queued and sent in the background for optimal performance.
    """

    def __init__(self, endpoint: str, org_id: str):
        self.endpoint = endpoint
        self.org_id = org_id
        self._queue: Queue = Queue(maxsize=MAX_QUEUE_SIZE)
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
                path, payload = event_data
                self._post(path, payload)
            except Exception as e:
                logger.error(f"Worker error: {e}")
            finally:
                self._queue.task_done()


    def _post(self, path: str, payload: Dict[str, Any]) -> bool:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._session.post(
                    f"{self.endpoint}{path}",
                    headers={
                        "Content-Type": "application/json",
                        "X-Org-Id": self.org_id,
                    },
                    json=payload,
                    timeout=10
                )
                if response.status_code < 500:
                    response.raise_for_status()
                    logger.debug(f"Sent {path}: {payload.get('event_id') or payload.get('session_id')}")
                    return True
                logger.warning(f"{path} returned {response.status_code} (attempt {attempt})")
            except requests.HTTPError as e:
                logger.error(f"{path} rejected: {e}")
                return False
            except Exception as e:
                logger.warning(f"{path} failed (attempt {attempt}): {e}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(0.5 * 2 ** (attempt - 1))
        logger.error(f"Dropping {path} after {MAX_ATTEMPTS} attempts")
        return False

    def queue_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Queue event for background processing.

        Args:
            event_data: Event data dictionary

        Returns:
            bool: True if queued successfully
        """
        return self._enqueue("/api/v1/capture-event", event_data)

    def queue_session(self, session_payload: Dict[str, Any]) -> bool:
        return self._enqueue("/api/v1/capture-session", session_payload)

    def _enqueue(self, path: str, payload: Dict[str, Any]) -> bool:
        try:
            self._queue.put((path, payload), block=False)
            logger.debug(f"Queued {path}")
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
        try:
            self._queue.put(None, block=False)
        except Full:
            pass

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

        self._session.close()
        logger.debug("EventProcessor shutdown complete")

    @property
    def queue_size(self) -> int:
        """Return current queue size."""
        return self._queue.qsize()
