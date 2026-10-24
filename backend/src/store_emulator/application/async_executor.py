"""Shared ThreadPoolExecutor for background work — simulation + layout/persona generation share this pool."""

from collections.abc import Callable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from threading import RLock

executor = ThreadPoolExecutor(max_workers=10)


def submit_background[**P](pool: Executor, function: Callable[P, None], /, *args: P.args, **kwargs: P.kwargs) -> Future[None]:
    """A rejected submission cannot later run a task already inserted in the pool's queue."""
    gate = RLock()
    canceled = False

    def accepted(*job_args: P.args, **job_kwargs: P.kwargs) -> None:
        with gate:
            if canceled:
                return
        function(*job_args, **job_kwargs)

    # ThreadPoolExecutor puts the task in its queue before starting a worker.
    with gate:
        try:
            return pool.submit(accepted, *args, **kwargs)
        except BaseException:
            canceled = True
            raise
