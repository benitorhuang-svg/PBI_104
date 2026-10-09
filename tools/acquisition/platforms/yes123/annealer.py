"""Adaptive annealing rate pacer with exponential backoff and circuit breaker.

Controls traffic velocity dynamically against target job servers:
1. Additive velocity increase (temperature cooling) on continuous healthy responses.
2. Latency-aware mild throttle on server degradation (> 3.5s response time).
3. Multiplicative decrease and exponential backoff with full jitter on HTTP 429/503/WAF.
4. Circuit breaker trips to protect IP reputation upon persistent consecutive errors.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional


class AnnealingPacer:
    """Dynamic rate pacer implementing simulated annealing and AIMD congestion control."""

    def __init__(
        self,
        min_interval: float = 1.5,
        max_interval: float = 15.0,
        initial_interval: float = 2.0,
        max_retries: int = 4,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.current_interval = initial_interval
        self.temperature = 0.1  # Range: [0.0, 1.0]
        self.consecutive_success = 0
        self.consecutive_errors = 0
        self.max_retries = max_retries
        self.cooldown_seconds = cooldown_seconds
        self.circuit_open_until = 0.0
        self._last_request_time = 0.0

    @property
    def is_circuit_open(self) -> bool:
        return time.time() < self.circuit_open_until

    def acquire(self) -> float:
        """Enforce sleep delay according to current interval and circuit state."""
        now = time.time()
        if now < self.circuit_open_until:
            wait_cb = self.circuit_open_until - now
            time.sleep(wait_cb)
            now = time.time()

        elapsed = now - self._last_request_time
        # Jitter added to interval to prevent deterministic cadence detection
        jittered_interval = self.current_interval + random.uniform(0.0, 0.4)
        if elapsed < jittered_interval:
            sleep_duration = jittered_interval - elapsed
            time.sleep(sleep_duration)
        self._last_request_time = time.time()
        return self.current_interval

    def on_success(self, latency: float) -> None:
        """Register successful response and apply adaptive cooling."""
        self.consecutive_errors = 0

        # Latency-aware mild throttle: server is slowing down
        if latency > 3.5:
            self.temperature = min(1.0, self.temperature + 0.15)
            self.current_interval = min(self.max_interval, self.current_interval + 0.3)
            self.consecutive_success = 0
            return

        # Healthy fast response: cool down temperature and accelerate gently
        self.consecutive_success += 1
        if self.consecutive_success >= 5:
            self.temperature = max(0.0, self.temperature - 0.05)
            self.current_interval = max(self.min_interval, self.current_interval - 0.1)
            self.consecutive_success = 0

    def on_throttle(
        self,
        status_code: int,
        retry_after: Optional[float] = None,
        reason: str = "",
    ) -> float:
        """Apply multiplicative decrease and return exponential backoff delay."""
        self.consecutive_errors += 1
        self.consecutive_success = 0
        self.temperature = min(1.0, self.temperature + 0.35)

        # Multiplicative decrease
        self.current_interval = min(
            self.max_interval,
            self.current_interval * 1.5 + 0.5,
        )

        if retry_after is not None and retry_after > 0:
            delay = retry_after
        else:
            exponent = min(self.consecutive_errors, 6)
            base = 2.0 * (2 ** (exponent - 1))
            delay = min(120.0, base + random.uniform(0.5, 2.5))

        if self.consecutive_errors >= self.max_retries:
            self.circuit_open_until = time.time() + self.cooldown_seconds

        time.sleep(delay)
        return delay

    def metrics(self) -> Dict[str, Any]:
        """Return diagnostic state dictionary."""
        return {
            "current_interval": round(self.current_interval, 2),
            "temperature": round(self.temperature, 2),
            "consecutive_success": self.consecutive_success,
            "consecutive_errors": self.consecutive_errors,
            "circuit_open": self.is_circuit_open,
        }
