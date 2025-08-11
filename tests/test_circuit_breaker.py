import asyncio
import logging

import pytest

from src.superego_mcp.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
)


class TestCircuitBreaker:
    """Test suite for circuit breaker functionality"""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker with test-friendly timeouts"""
        return CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=2,  # Short timeout for testing
            timeout_seconds=1,  # Short timeout for testing
        )

    @pytest.fixture
    def successful_func(self):
        """Mock function that always succeeds"""

        async def success():
            return "success"

        return success

    @pytest.fixture
    def failing_func(self):
        """Mock function that always fails"""

        async def fail():
            raise ValueError("Service error")

        return fail

    @pytest.fixture
    def slow_func(self):
        """Mock function that times out"""

        async def slow():
            await asyncio.sleep(2)  # Longer than timeout
            return "slow"

        return slow

    def test_circuit_breaker_starts_closed(self, circuit_breaker):
        """Test that circuit breaker starts in closed state"""
        state = circuit_breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["last_failure_time"] is None
        assert state["failure_threshold"] == 5
        assert state["recovery_timeout"] == 2

    @pytest.mark.asyncio
    async def test_successful_call_in_closed_state(
        self, circuit_breaker, successful_func
    ):
        """Test successful call maintains closed state"""
        result = await circuit_breaker.call(successful_func)
        assert result == "success"

        state = circuit_breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_failure_increments_count(self, circuit_breaker, failing_func):
        """Test that failures increment failure count"""
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

        state = circuit_breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 1
        assert state["last_failure_time"] is not None

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold_failures(
        self, circuit_breaker, failing_func
    ):
        """Test circuit breaker opens after configured failure threshold"""
        # Cause 5 failures to reach threshold
        for i in range(5):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)

        state = circuit_breaker.get_state()
        assert state["state"] == "open"
        assert state["failure_count"] == 5

    @pytest.mark.asyncio
    async def test_open_circuit_raises_circuit_breaker_error(
        self, circuit_breaker, failing_func, successful_func
    ):
        """Test that open circuit raises CircuitBreakerOpenError"""
        # Open the circuit
        for i in range(5):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)

        # Now calls should raise CircuitBreakerOpenError
        with pytest.raises(
            CircuitBreakerOpenError,
            match="AI service unavailable - circuit breaker open",
        ):
            await circuit_breaker.call(successful_func)

    @pytest.mark.asyncio
    async def test_circuit_enters_half_open_after_recovery_timeout(
        self, circuit_breaker, failing_func
    ):
        """Test circuit breaker transitions to half-open after recovery timeout"""
        # Open the circuit
        for i in range(5):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)

        # Wait for recovery timeout
        await asyncio.sleep(2.1)  # Slightly longer than recovery timeout

        # Create a mock function to verify half-open state
        async def check_state():
            return "half_open_test"

        # This should transition to half-open and succeed
        result = await circuit_breaker.call(check_state)
        assert result == "half_open_test"

        state = circuit_breaker.get_state()
        assert state["state"] == "closed"  # Should reset to closed after success

    @pytest.mark.asyncio
    async def test_successful_call_in_half_open_resets_to_closed(
        self, circuit_breaker, failing_func, successful_func
    ):
        """Test successful call in half-open state resets to closed"""
        # Open the circuit
        for i in range(5):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)

        # Wait for recovery timeout
        await asyncio.sleep(2.1)

        # Successful call should reset to closed
        result = await circuit_breaker.call(successful_func)
        assert result == "success"

        state = circuit_breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["last_failure_time"] is None

    @pytest.mark.asyncio
    async def test_failed_call_in_half_open_returns_to_open(
        self, circuit_breaker, failing_func
    ):
        """Test failed call in half-open state returns to open"""
        # Open the circuit
        for i in range(5):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)

        # Wait for recovery timeout
        await asyncio.sleep(2.1)

        # Failed call should return to open
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

        state = circuit_breaker.get_state()
        assert state["state"] == "open"

    @pytest.mark.asyncio
    async def test_timeout_raises_circuit_breaker_open_error(
        self, circuit_breaker, slow_func
    ):
        """Test async timeout raises CircuitBreakerOpenError"""
        with pytest.raises(CircuitBreakerOpenError, match="AI service timeout"):
            await circuit_breaker.call(slow_func)

        state = circuit_breaker.get_state()
        assert state["failure_count"] == 1

    @pytest.mark.asyncio
    async def test_timeout_contributes_to_failure_count(
        self, circuit_breaker, slow_func
    ):
        """Test that timeouts contribute to failure count and can open circuit"""
        # Cause 5 timeouts to open circuit
        for i in range(5):
            with pytest.raises(CircuitBreakerOpenError, match="AI service timeout"):
                await circuit_breaker.call(slow_func)

        state = circuit_breaker.get_state()
        assert state["state"] == "open"
        assert state["failure_count"] == 5

    @pytest.mark.asyncio
    async def test_get_state_returns_accurate_monitoring_data(
        self, circuit_breaker, failing_func
    ):
        """Test get_state returns accurate monitoring data"""
        # Initial state
        state = circuit_breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["last_failure_time"] is None
        assert state["failure_threshold"] == 5
        assert state["recovery_timeout"] == 2

        # After one failure
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

        state = circuit_breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 1
        assert isinstance(state["last_failure_time"], float)
        assert state["last_failure_time"] > 0

    @pytest.mark.asyncio
    async def test_logging_behavior(
        self, circuit_breaker, failing_func, successful_func, caplog
    ):
        """Test proper logging behavior for state transitions"""
        caplog.set_level(logging.INFO)

        # Open circuit
        for i in range(5):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)

        # Check that opening was logged
        assert "Circuit breaker opened after 5 failures" in caplog.text

        # Clear logs
        caplog.clear()

        # Wait for recovery and make successful call
        await asyncio.sleep(2.1)
        await circuit_breaker.call(successful_func)

        # Check transition logs
        assert "Circuit breaker entering half-open state" in caplog.text
        assert "Circuit breaker reset to closed state" in caplog.text

    @pytest.mark.asyncio
    async def test_exception_propagation(self, circuit_breaker):
        """Test that original exceptions are properly propagated"""

        async def custom_error_func():
            raise ValueError("Custom error message")

        # Should propagate the original exception
        with pytest.raises(ValueError, match="Custom error message"):
            await circuit_breaker.call(custom_error_func)

    @pytest.mark.asyncio
    async def test_concurrent_calls_thread_safety(
        self, circuit_breaker, successful_func
    ):
        """Test circuit breaker behavior under concurrent calls"""

        async def make_call():
            return await circuit_breaker.call(successful_func)

        # Make 10 concurrent calls
        tasks = [make_call() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(result == "success" for result in results)

        state = circuit_breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure_behavior(
        self, circuit_breaker, successful_func, failing_func
    ):
        """Test mixed success and failure scenarios"""
        # 3 failures (below threshold)
        for i in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)

        # 1 success (should reset count)
        result = await circuit_breaker.call(successful_func)
        assert result == "success"

        state = circuit_breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 0

        # Now it should take 5 more failures to open
        for i in range(5):
            with pytest.raises(ValueError):
                await circuit_breaker.call(failing_func)

        state = circuit_breaker.get_state()
        assert state["state"] == "open"

    def test_custom_configuration(self):
        """Test circuit breaker with custom configuration"""
        cb = CircuitBreaker(
            failure_threshold=3, recovery_timeout=60, timeout_seconds=30
        )

        state = cb.get_state()
        assert state["failure_threshold"] == 3
        assert state["recovery_timeout"] == 60
        assert cb.timeout_seconds == 30
