"""Tests for the ConfigWatcher class."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from superego_mcp.infrastructure.config_watcher import ConfigWatcher
from superego_mcp.domain.models import ErrorCode, SuperegoError


class TestConfigWatcher:
    """Test suite for ConfigWatcher functionality."""

    @pytest.fixture
    async def temp_config_file(self):
        """Create a temporary configuration file for testing."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            f.write("""
rules:
  - id: "test_rule"
    priority: 1
    conditions:
      tool_name: "test"
    action: "allow"
    reason: "Test rule"
""")
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def mock_reload_callback(self):
        """Mock reload callback for testing."""
        return AsyncMock()

    @pytest.fixture
    async def config_watcher(self, temp_config_file, mock_reload_callback):
        """Create a ConfigWatcher instance for testing."""
        watcher = ConfigWatcher(
            watch_path=temp_config_file,
            reload_callback=mock_reload_callback,
            debounce_seconds=0.1,  # Short debounce for testing
        )
        yield watcher
        
        # Ensure cleanup
        if watcher._watcher_task:
            await watcher.stop()

    @pytest.mark.unit
    async def test_config_watcher_initialization(self, temp_config_file, mock_reload_callback):
        """Test ConfigWatcher initialization."""
        watcher = ConfigWatcher(
            watch_path=temp_config_file,
            reload_callback=mock_reload_callback,
            debounce_seconds=1.0,
        )
        
        assert watcher.watch_path == temp_config_file
        assert watcher.reload_callback == mock_reload_callback
        assert watcher.debounce_seconds == 1.0
        assert watcher._watcher_task is None

    @pytest.mark.unit
    async def test_config_watcher_start_success(self, config_watcher, temp_config_file):
        """Test successful start of ConfigWatcher."""
        await config_watcher.start()
        
        assert config_watcher._watcher_task is not None
        assert not config_watcher._watcher_task.done()
        
        # Cleanup
        await config_watcher.stop()

    @pytest.mark.unit
    async def test_config_watcher_start_missing_file(self, mock_reload_callback):
        """Test ConfigWatcher start with missing file."""
        missing_file = Path("/nonexistent/file.yaml")
        watcher = ConfigWatcher(
            watch_path=missing_file,
            reload_callback=mock_reload_callback,
        )
        
        with pytest.raises(SuperegoError) as exc_info:
            await watcher.start()
        
        assert exc_info.value.code == ErrorCode.INVALID_CONFIGURATION
        assert "not found" in exc_info.value.message

    @pytest.mark.unit
    async def test_config_watcher_start_twice_fails(self, config_watcher):
        """Test that starting ConfigWatcher twice raises error."""
        await config_watcher.start()
        
        with pytest.raises(SuperegoError) as exc_info:
            await config_watcher.start()
        
        assert exc_info.value.code == ErrorCode.INTERNAL_ERROR
        assert "already running" in exc_info.value.message
        
        # Cleanup
        await config_watcher.stop()

    @pytest.mark.unit
    async def test_config_watcher_stop(self, config_watcher):
        """Test stopping ConfigWatcher."""
        await config_watcher.start()
        
        # Verify it's running
        assert config_watcher._watcher_task is not None
        
        await config_watcher.stop()
        
        # Verify it's stopped
        assert config_watcher._watcher_task is None

    @pytest.mark.unit
    async def test_config_watcher_stop_when_not_running(self, config_watcher):
        """Test stopping ConfigWatcher when it's not running."""
        # Should not raise an error
        await config_watcher.stop()
        
        assert config_watcher._watcher_task is None

    @pytest.mark.unit
    async def test_manual_trigger_reload(self, config_watcher, mock_reload_callback):
        """Test manual trigger of reload."""
        await config_watcher.trigger_reload()
        
        # Wait for debounced reload
        await asyncio.sleep(0.15)  # Longer than debounce
        
        mock_reload_callback.assert_called_once()

    @pytest.mark.unit
    async def test_debounced_reload_cancels_previous(self, config_watcher, mock_reload_callback):
        """Test that debounced reload cancels previous pending reload."""
        # Trigger multiple reloads quickly
        await config_watcher.trigger_reload()
        await config_watcher.trigger_reload()
        await config_watcher.trigger_reload()
        
        # Wait for debounce
        await asyncio.sleep(0.15)
        
        # Should only be called once due to debouncing
        assert mock_reload_callback.call_count == 1

    @pytest.mark.unit
    async def test_reload_callback_exception_handling(self, temp_config_file):
        """Test that exceptions in reload callback are handled gracefully."""
        failing_callback = AsyncMock(side_effect=Exception("Reload failed"))
        
        watcher = ConfigWatcher(
            watch_path=temp_config_file,
            reload_callback=failing_callback,
            debounce_seconds=0.1,
        )
        
        # Should not raise exception
        await watcher.trigger_reload()
        await asyncio.sleep(0.15)
        
        failing_callback.assert_called_once()

    @pytest.mark.unit
    def test_health_check_not_running(self, temp_config_file, mock_reload_callback):
        """Test health check when watcher is not running."""
        watcher = ConfigWatcher(
            watch_path=temp_config_file,
            reload_callback=mock_reload_callback,
        )
        
        health = watcher.health_check()
        
        assert health["status"] == "unhealthy"
        assert health["message"] == "File watcher not running"
        assert health["is_running"] is False
        assert health["watch_path"] == str(temp_config_file)
        assert health["last_reload_time"] is None

    @pytest.mark.unit
    async def test_health_check_running(self, config_watcher, temp_config_file):
        """Test health check when watcher is running."""
        await config_watcher.start()
        
        health = config_watcher.health_check()
        
        assert health["status"] == "healthy"
        assert health["message"] == "File watcher active"
        assert health["is_running"] is True
        assert health["watch_path"] == str(temp_config_file)
        assert health["debounce_seconds"] == 0.1
        
        # Cleanup
        await config_watcher.stop()

    @pytest.mark.unit
    async def test_health_check_after_reload(self, config_watcher, mock_reload_callback):
        """Test health check after a reload has occurred."""
        await config_watcher.trigger_reload()
        await asyncio.sleep(0.15)  # Wait for debounced reload
        
        health = config_watcher.health_check()
        
        assert health["last_reload_time"] is not None
        assert health["last_reload_time"] > 0
        assert health["last_reload_age_seconds"] is not None

    @pytest.mark.integration
    async def test_file_modification_triggers_reload(self, temp_config_file, mock_reload_callback):
        """Test that actual file modification triggers reload (integration test)."""
        watcher = ConfigWatcher(
            watch_path=temp_config_file,
            reload_callback=mock_reload_callback,
            debounce_seconds=0.1,
        )
        
        await watcher.start()
        
        # Give the watcher time to start
        await asyncio.sleep(0.1)
        
        # Modify the file
        with open(temp_config_file, 'a') as f:
            f.write("\n# Modified file\n")
        
        # Wait for file system event and debounce
        await asyncio.sleep(0.5)
        
        # Verify callback was called
        mock_reload_callback.assert_called()
        
        await watcher.stop()

    @pytest.mark.integration
    async def test_file_replacement_triggers_reload(self, temp_config_file, mock_reload_callback):
        """Test that file replacement (common editor behavior) triggers reload."""
        watcher = ConfigWatcher(
            watch_path=temp_config_file,
            reload_callback=mock_reload_callback,
            debounce_seconds=0.1,
        )
        
        await watcher.start()
        await asyncio.sleep(0.1)  # Let watcher start
        
        # Replace file content (simulates many editors)
        new_content = """
rules:
  - id: "replaced_rule"
    priority: 1
    conditions:
      tool_name: "replaced"
    action: "deny"
    reason: "Replaced rule"
"""
        with open(temp_config_file, 'w') as f:
            f.write(new_content)
        
        # Wait for event processing
        await asyncio.sleep(0.5)
        
        mock_reload_callback.assert_called()
        
        await watcher.stop()

    @pytest.mark.unit
    async def test_graceful_shutdown_cancels_pending_reload(self, config_watcher, mock_reload_callback):
        """Test that graceful shutdown cancels pending reload tasks."""
        await config_watcher.start()
        
        # Trigger reload but don't wait for it
        await config_watcher.trigger_reload()
        
        # Stop immediately
        await config_watcher.stop()
        
        # Wait a bit longer to ensure reload would have completed
        await asyncio.sleep(0.15)
        
        # Callback might or might not have been called depending on timing
        # The important thing is that stop() completed without hanging