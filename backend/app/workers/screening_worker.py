"""Background screening worker and WorkerManager for D-DATO.

Phase P12: Provides in-process background worker execution using concurrent.futures.ThreadPoolExecutor.
Maintains clean separation from the synchronous P11 pipeline.
Thread-safe, process-local future tracking, duplicate submission protection, and graceful shutdown.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class DuplicateRunSubmissionError(Exception):
    """Raised when attempting to submit a run that is already queued or executing."""
    pass


class WorkerManager:
    """Thread-safe worker manager wrapping ThreadPoolExecutor for background screening runs.

    Responsibilities:
    - Manage standard library in-process worker pool.
    - Submit runs asynchronously.
    - Track active in-process futures by run_id.
    - Prevent duplicate submissions of active runs.
    - Report execution activity.
    - Provide graceful shutdown without orphaned threads.
    """

    def __init__(self, max_concurrency: Optional[int] = None):
        self.max_concurrency = max_concurrency if max_concurrency is not None else settings.WORKER_MAX_CONCURRENCY
        if self.max_concurrency < 1:
            raise ValueError(f"max_concurrency must be >= 1, got {self.max_concurrency}")

        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: Dict[str, Future] = {}
        self._lock = threading.RLock()
        self._is_shutdown: bool = False

    def start(self) -> None:
        """Initialize the underlying ThreadPoolExecutor if not already running."""
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Cannot start WorkerManager after it has been shut down.")
            if self._executor is None:
                logger.info(
                    "Starting WorkerManager ThreadPoolExecutor (max_concurrency=%d)",
                    self.max_concurrency,
                )
                self._executor = ThreadPoolExecutor(
                    max_workers=self.max_concurrency,
                    thread_name_prefix="ddato-screening-worker",
                )

    def submit(
        self,
        run_id: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Future:
        """Submit a screening task to the background executor.

        Args:
            run_id: Unique string identifier for the screening run.
            fn: Callable target function to execute in the worker thread.
            *args: Positional arguments for fn.
            **kwargs: Keyword arguments for fn.

        Returns:
            Future representing the submitted background execution.

        Raises:
            DuplicateRunSubmissionError: If run_id is currently queued or executing.
            RuntimeError: If WorkerManager is shut down.
        """
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("WorkerManager has been shut down and cannot accept new tasks.")

            if run_id in self._futures and not self._futures[run_id].done():
                raise DuplicateRunSubmissionError(
                    f"Run '{run_id}' is already queued or actively executing."
                )

            if self._executor is None:
                logger.info(
                    "Lazily starting WorkerManager ThreadPoolExecutor (max_concurrency=%d)",
                    self.max_concurrency,
                )
                self._executor = ThreadPoolExecutor(
                    max_workers=self.max_concurrency,
                    thread_name_prefix="ddato-screening-worker",
                )

            logger.info("Submitting run '%s' to background worker queue", run_id)
            future = self._executor.submit(fn, *args, **kwargs)
            self._futures[run_id] = future

            # Attach finalizer callback to clean up tracking dictionary upon completion
            future.add_done_callback(lambda f: self._on_task_done(run_id, f))
            return future

    def _on_task_done(self, run_id: str, future: Future) -> None:
        """Callback invoked when a worker task completes or raises."""
        with self._lock:
            if run_id in self._futures and self._futures[run_id] is future:
                self._futures.pop(run_id, None)

        try:
            exc = future.exception()
            if exc is not None:
                logger.error(
                    "Unhandled exception in background worker execution for run '%s': %s",
                    run_id,
                    exc,
                    exc_info=exc,
                )
        except Exception as callback_err:
            logger.warning(
                "Error checking future exception for run '%s': %s", run_id, callback_err
            )

    def is_active(self, run_id: str) -> bool:
        """Check whether a run is currently queued or actively executing."""
        with self._lock:
            return run_id in self._futures and not self._futures[run_id].done()

    def is_running(self, run_id: str) -> bool:
        """Alias for is_active."""
        return self.is_active(run_id)

    def get_active_run_ids(self) -> List[str]:
        """Return a snapshot list of run IDs currently active in the worker manager."""
        with self._lock:
            return [rid for rid, f in self._futures.items() if not f.done()]

    def get_future(self, run_id: str) -> Optional[Future]:
        """Return the Future associated with an active run, or None if inactive."""
        with self._lock:
            return self._futures.get(run_id)

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """Gracefully shut down the worker executor.

        Args:
            wait: If True, blocks until all running tasks complete.
            cancel_futures: If True, cancels pending queued tasks that have not yet started.
        """
        with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
            executor = self._executor
            self._executor = None

        if executor is not None:
            logger.info("Shutting down WorkerManager ThreadPoolExecutor (wait=%s)", wait)
            executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        logger.info("WorkerManager shutdown complete.")


# Process-local singleton instance
_global_worker_manager: Optional[WorkerManager] = None
_global_lock = threading.RLock()


def get_worker_manager(max_concurrency: Optional[int] = None) -> WorkerManager:
    """Return the application-wide singleton WorkerManager instance."""
    global _global_worker_manager
    with _global_lock:
        if _global_worker_manager is None or _global_worker_manager._is_shutdown:
            _global_worker_manager = WorkerManager(max_concurrency=max_concurrency)
        return _global_worker_manager


def reset_global_worker_manager(wait: bool = True) -> None:
    """Reset and shut down the global worker manager (used in test teardown)."""
    global _global_worker_manager
    with _global_lock:
        if _global_worker_manager is not None:
            _global_worker_manager.shutdown(wait=wait)
            _global_worker_manager = None


class ScreeningWorker:
    """Legacy compatibility facade delegating to WorkerManager."""

    def __init__(self, manager: Optional[WorkerManager] = None):
        self.manager = manager or get_worker_manager()

    def process_screening_job(
        self, run_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Future:
        return self.manager.submit(run_id, fn, *args, **kwargs)
