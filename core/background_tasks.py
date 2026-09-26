from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import threading
import uuid

from core.events import EVENT_BUS, EventBus, EventType
from core.tool_registry import AVAILABLE_FUNCTIONS


class TaskStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class _Task:
    task_id: str
    tool_name: str
    status: str = TaskStatus.PENDING
    future: Future | None = None


class BackgroundTaskManager:
    def __init__(
        self,
        max_concurrent_tasks: int = 2,
        approved_functions: dict | None = None,
        event_bus: EventBus = EVENT_BUS,
    ):
        if max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be at least 1")

        self.max_concurrent_tasks = max_concurrent_tasks
        self._approved_functions = (
            approved_functions
            if approved_functions is not None
            else AVAILABLE_FUNCTIONS
        )
        self._event_bus = event_bus
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent_tasks,
        )
        self._tasks: dict[str, _Task] = {}
        self._statuses: dict[str, str] = {}
        self._running_count = 0
        self._lock = threading.Lock()

    def start_task(
        self,
        tool_name: str,
        args: tuple = (),
        kwargs: dict | None = None,
        task_id: str | None = None,
    ) -> str:
        if not isinstance(tool_name, str) or tool_name not in self._approved_functions:
            raise ValueError("Only registered tools may run in the background.")

        if not isinstance(args, tuple):
            raise TypeError("args must be a tuple")

        if kwargs is None:
            kwargs = {}

        if not isinstance(kwargs, dict):
            raise TypeError("kwargs must be a dictionary")

        task_id = task_id or uuid.uuid4().hex

        with self._lock:
            if task_id in self._tasks or task_id in self._statuses:
                raise ValueError(f"Duplicate task ID: {task_id}")

            task = _Task(task_id, tool_name)
            self._tasks[task_id] = task
            self._statuses[task_id] = TaskStatus.PENDING

        try:
            future = self._executor.submit(
                self._run_task,
                task,
                self._approved_functions[tool_name],
                args,
                kwargs,
            )
        except Exception:
            with self._lock:
                self._tasks.pop(task_id, None)
                self._statuses.pop(task_id, None)
            raise

        with self._lock:
            task.future = future

        future.add_done_callback(
            lambda completed_future: self._finish_task(
                task,
                completed_future,
            )
        )

        return task_id

    def _run_task(self, task, function, args, kwargs):
        with self._lock:
            if task.status == TaskStatus.PENDING:
                self._running_count += 1
                task.status = TaskStatus.RUNNING
                self._statuses[task.task_id] = TaskStatus.RUNNING

        self._event_bus.emit(
            EventType.TASK_STARTED,
            task_id=task.task_id,
            tool=task.tool_name,
        )

        return function(*args, **kwargs)

    def _finish_task(self, task, future):
        if future.cancelled():
            status = TaskStatus.CANCELLED
            event_type = EventType.TASK_CANCELLED
        else:
            try:
                future.result()
            except Exception:
                status = TaskStatus.FAILED
                event_type = EventType.TASK_FAILED
            else:
                status = TaskStatus.COMPLETED
                event_type = EventType.TASK_COMPLETED

        with self._lock:
            if task.status == TaskStatus.RUNNING:
                self._running_count -= 1
            task.status = status
            self._statuses[task.task_id] = status
            self._tasks.pop(task.task_id, None)

        self._event_bus.emit(
            event_type,
            task_id=task.task_id,
            tool=task.tool_name,
        )

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)

            if task is None or task.future is None:
                return False

            future = task.future

        return future.cancel()

    def get_status(self, task_id: str) -> str | None:
        with self._lock:
            return self._statuses.get(task_id)

    def cleanup_completed(self) -> None:
        with self._lock:
            completed_statuses = {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }
            task_ids = [
                task_id
                for task_id, status in self._statuses.items()
                if status in completed_statuses
            ]

            for task_id in task_ids:
                self._statuses.pop(task_id, None)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)