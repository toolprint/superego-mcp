import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, Literal


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""

    pass


class CircuitBreaker:
    """Prevents cascade failures from AI service outages"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        timeout_seconds: int = 10,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state: Literal["closed", "open", "half_open"] = "closed"
        self.logger = logging.getLogger(__name__)

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
                self.logger.info("Circuit breaker entering half-open state")
            else:
                raise CircuitBreakerOpenError(
                    "AI service unavailable - circuit breaker open"
                )

        try:
            async with asyncio.timeout(self.timeout_seconds):
                result = await func(*args, **kwargs)
                self._on_success()
                return result

        except TimeoutError:
            self.logger.error(
                f"AI service call timed out after {self.timeout_seconds}s"
            )
            self._on_failure()
            raise CircuitBreakerOpenError("AI service timeout") from None

        except Exception as e:
            self.logger.error(f"AI service call failed: {e}")
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful operation"""
        if self.state in ["half_open", "open"]:
            self.logger.info("Circuit breaker reset to closed state")

        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None

    def _on_failure(self) -> None:
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )
        elif self.state == "half_open":
            self.state = "open"
            self.logger.warning("Circuit breaker returned to open state")

    def get_state(self) -> dict:
        """Get current circuit breaker state for monitoring"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
