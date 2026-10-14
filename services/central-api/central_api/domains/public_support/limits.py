"""Bounded admission counters for the single-instance portfolio deployment."""

import threading
import time
from collections import deque
from datetime import UTC, datetime


class AdmissionLimit(Exception):
    pass


class SupportAdmission:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.minute: deque[float] = deque(maxlen=30)
        self.day = datetime.now(UTC).date()
        self.daily_count = 0

    def acquire(self) -> None:
        with self.lock:
            now = time.monotonic()
            day = datetime.now(UTC).date()
            if day != self.day:
                self.day, self.daily_count = day, 0
            while self.minute and self.minute[0] <= now - 60:
                self.minute.popleft()
            if self.active >= 2 or len(self.minute) >= 30 or self.daily_count >= 200:
                raise AdmissionLimit
            self.active += 1
            self.daily_count += 1
            self.minute.append(now)

    def release(self) -> None:
        with self.lock:
            self.active -= 1
