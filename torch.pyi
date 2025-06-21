# Minimal *local* stub for the ``torch`` package.
# This is only used by *mypy* during static analysis in CI. The actual
# runtime dependency remains the real PyTorch installation.
from typing import Any, TypeVar

_T = TypeVar("_T")

def cuda_is_available() -> bool:  # pragma: no cover
    ...

class cuda:  # noqa: D401 – namespace stub
    @staticmethod
    def is_available() -> bool:
        ...

    @staticmethod
    def empty_cache() -> None:
        ...

Tensor = Any 