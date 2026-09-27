from collections.abc import Callable


class JobCancelled(Exception):
    """A user requested cancellation at a safe processing boundary."""


def check_cancelled(cancelled: Callable[[], bool] | None = None) -> None:
    if cancelled and cancelled():
        raise JobCancelled("작업을 중지했습니다. 완료된 파일은 보관됩니다.")
