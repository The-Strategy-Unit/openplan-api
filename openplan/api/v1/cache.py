from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future
from threading import Lock
from time import monotonic

from openplan.api.v1.settings import CacheSettings

BlobKey = tuple[str, str, str]


class BlobCache:
    """Bound downloaded bytes by age and size; share concurrent loads per key."""

    MAX_ENTRIES = 1024

    def __init__(self, clock: Callable[[], float] = monotonic):
        self._clock = clock
        self._lock = Lock()
        self._entries: OrderedDict[BlobKey, tuple[float, bytes]] = OrderedDict()
        self._pending: dict[tuple[int, BlobKey], Future[bytes]] = {}
        self._size = 0
        self._generation = 0
        self._policy: CacheSettings | None = None

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._size = 0
            # Downloads already in progress must not repopulate a cleared cache.
            self._generation += 1

    def _expire(self, now: float) -> None:
        expired = [key for key, (deadline, _) in self._entries.items() if deadline <= now]
        for key in expired:
            _, payload = self._entries.pop(key)
            self._size -= len(payload)

    def get(self, key: BlobKey, load: Callable[[], bytes], policy: CacheSettings) -> bytes:
        with self._lock:
            if policy != self._policy:
                self._entries.clear()
                self._size = 0
                self._generation += 1
                self._policy = policy
            generation = self._generation
            self._expire(self._clock())
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key][1]
            pending_key = (generation, key)
            future = self._pending.get(pending_key)
            if future is None:
                owner = True
                future = Future()
                self._pending[pending_key] = future
            else:
                owner = False

        if not owner:
            return future.result()

        try:
            payload = load()
            with self._lock:
                if generation == self._generation and policy.ttl_seconds > 0 and policy.max_bytes > 0:
                    now = self._clock()
                    self._expire(now)
                    if len(payload) <= policy.max_bytes:
                        while self._entries and (
                            self._size + len(payload) > policy.max_bytes
                            or len(self._entries) >= self.MAX_ENTRIES
                        ):
                            _, (_, evicted) = self._entries.popitem(last=False)
                            self._size -= len(evicted)
                        self._entries[key] = (now + policy.ttl_seconds, payload)
                        self._size += len(payload)
            future.set_result(payload)
            return payload
        except BaseException as exc:
            # Release waiting requests even if the downloading thread aborts.
            future.set_exception(exc)
            raise
        finally:
            with self._lock:
                self._pending.pop(pending_key, None)
