from abc import (
    ABCMeta,
    abstractmethod,
)
from typing import (
    Iterable,
    List,
    Optional,
)


from monkeytype.tracing import CallTrace


class CallTraceThunk(metaclass=ABCMeta):
    """A deferred computation that produces a CallTrace or raises an error."""

    @abstractmethod
    def to_trace(self) -> CallTrace:
        """Produces the CallTrace."""
        pass


class CallTraceStore(metaclass=ABCMeta):
    """An interface that all concrete calltrace storage backends must implement."""

    @abstractmethod
    def add(self, traces: Iterable[CallTrace]) -> None:
        """Store the supplied call traces in the backing store"""
        pass

    @abstractmethod
    def filter(
        self,
        module: str,
        qualname_prefix: Optional[str] = None,
        limit: int = 2000
    ) -> List[CallTraceThunk]:
        """Query the backing store for any traces that match the supplied query.

        By returning a list of thunks we let the caller get a partial result in the
        event that decoding one or more call traces fails.
        """
        pass
