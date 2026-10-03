"""Unit tests for WorkerManager and ScreeningWorker (Phase P12)."""

import threading
import time
from typing import List
import pytest

from app.workers.screening_worker import (
    DuplicateRunSubmissionError,
    ScreeningWorker,
    WorkerManager,
    get_worker_manager,
    reset_global_worker_manager,
)


@pytest.fixture(autouse=True)
def cleanup_worker():
    """Ensure global worker manager is shut down after each test."""
    yield
    reset_global_worker_manager(wait=True)


def test_worker_task_submission():
    """Verify task submission and execution through WorkerManager."""
    manager = WorkerManager(max_concurrency=1)
    try:
        def compute_sum(a: int, b: int) -> int:
            return a + b

        future = manager.submit("run-1", compute_sum, 10, 20)
        result = future.result(timeout=2.0)
        assert result == 30
    finally:
        manager.shutdown(wait=True)


def test_worker_future_tracking():
    """Verify in-process future tracking while a task is running."""
    manager = WorkerManager(max_concurrency=1)
    start_event = threading.Event()
    continue_event = threading.Event()

    def blocked_task():
        start_event.set()
        continue_event.wait(timeout=3.0)
        return "done"

    try:
        future = manager.submit("run-active", blocked_task)
        assert start_event.wait(timeout=2.0)

        assert manager.is_active("run-active") is True
        assert manager.is_running("run-active") is True
        assert manager.get_active_run_ids() == ["run-active"]
        assert manager.get_future("run-active") is future

        continue_event.set()
        assert future.result(timeout=2.0) == "done"

        # After completion, tracking should be removed
        time.sleep(0.05)
        assert manager.is_active("run-active") is False
        assert manager.get_active_run_ids() == []
    finally:
        continue_event.set()
        manager.shutdown(wait=True)


def test_worker_duplicate_run_rejection():
    """Verify duplicate submission of an active run_id raises DuplicateRunSubmissionError."""
    manager = WorkerManager(max_concurrency=2)
    start_event = threading.Event()
    continue_event = threading.Event()

    def slow_task():
        start_event.set()
        continue_event.wait(timeout=3.0)

    try:
        manager.submit("run-dup", slow_task)
        assert start_event.wait(timeout=2.0)

        with pytest.raises(DuplicateRunSubmissionError) as exc_info:
            manager.submit("run-dup", slow_task)

        assert "already queued or actively executing" in str(exc_info.value)
    finally:
        continue_event.set()
        manager.shutdown(wait=True)


def test_worker_execution_callback():
    """Verify task completion callback cleanly cleans up tracking dictionary."""
    manager = WorkerManager(max_concurrency=1)
    try:
        future = manager.submit("run-cb", lambda: 42)
        assert future.result(timeout=2.0) == 42
        time.sleep(0.05)
        assert manager.is_active("run-cb") is False
        assert manager.get_future("run-cb") is None
    finally:
        manager.shutdown(wait=True)


def test_worker_unhandled_exception_logged():
    """Verify exceptions in worker tasks are captured on Future and do not break the manager."""
    manager = WorkerManager(max_concurrency=1)
    try:
        def failing_task():
            raise RuntimeError("Deliberate background task error")

        future = manager.submit("run-err", failing_task)
        with pytest.raises(RuntimeError) as exc_info:
            future.result(timeout=2.0)

        assert "Deliberate background task error" in str(exc_info.value)
        time.sleep(0.05)
        assert manager.is_active("run-err") is False
    finally:
        manager.shutdown(wait=True)


def test_worker_shutdown_behavior():
    """Verify WorkerManager cannot accept submissions after shutdown."""
    manager = WorkerManager(max_concurrency=1)
    manager.shutdown(wait=True)

    with pytest.raises(RuntimeError) as exc_info:
        manager.submit("run-post-shutdown", lambda: 1)

    assert "shut down" in str(exc_info.value).lower()


def test_worker_executor_concurrency_setting():
    """Verify custom max_concurrency setting is respected."""
    manager = WorkerManager(max_concurrency=3)
    try:
        assert manager.max_concurrency == 3
        manager.start()
        assert manager._executor._max_workers == 3
    finally:
        manager.shutdown(wait=True)


def test_worker_invalid_concurrency_rejected():
    """Verify non-positive concurrency is rejected with ValueError."""
    with pytest.raises(ValueError):
        WorkerManager(max_concurrency=0)

    with pytest.raises(ValueError):
        WorkerManager(max_concurrency=-2)


def test_worker_concurrency_serialization():
    """Verify max_concurrency=1 executes tasks strictly sequentially."""
    manager = WorkerManager(max_concurrency=1)
    execution_order: List[str] = []
    task1_started = threading.Event()
    task1_release = threading.Event()

    def task1():
        execution_order.append("task1_start")
        task1_started.set()
        task1_release.wait(timeout=3.0)
        execution_order.append("task1_end")

    def task2():
        execution_order.append("task2_start")
        execution_order.append("task2_end")

    try:
        f1 = manager.submit("run-1", task1)
        assert task1_started.wait(timeout=2.0)

        f2 = manager.submit("run-2", task2)

        # While task1 is blocked, task2 cannot have started because concurrency is 1
        assert "task2_start" not in execution_order

        task1_release.set()
        f1.result(timeout=2.0)
        f2.result(timeout=2.0)

        assert execution_order == ["task1_start", "task1_end", "task2_start", "task2_end"]
    finally:
        task1_release.set()
        manager.shutdown(wait=True)


def test_screening_worker_facade():
    """Verify legacy ScreeningWorker facade delegates to WorkerManager."""
    worker = ScreeningWorker()
    try:
        future = worker.process_screening_job("run-facade", lambda: "success")
        assert future.result(timeout=2.0) == "success"
    finally:
        worker.manager.shutdown(wait=True)
