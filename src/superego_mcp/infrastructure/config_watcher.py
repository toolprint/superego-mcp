"""Configuration file watcher for hot-reload functionality."""

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import structlog
from watchfiles import awatch

from ..domain.models import ErrorCode, SuperegoError


class ConfigWatcher:
    """File system watcher for configuration hot-reload with debouncing."""

    def __init__(
        self,
        watch_path: Path,
        reload_callback: Callable[[], Coroutine[Any, Any, None]],
        debounce_seconds: float = 1.0,
    ):
        """Initialize the config watcher.

        Args:
            watch_path: Path to the configuration file to monitor
            reload_callback: Async callback to execute on file changes
            debounce_seconds: Minimum delay between reload attempts
        """
        self.watch_path = watch_path
        self.reload_callback = reload_callback
        self.debounce_seconds = debounce_seconds
        self.logger = structlog.get_logger(__name__)
        self._watcher_task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()
        self._last_reload_time = 0.0
        self._pending_reload_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start watching the configuration file for changes."""
        if self._watcher_task is not None:
            raise SuperegoError(
                ErrorCode.INTERNAL_ERROR,
                "ConfigWatcher is already running",
                "File watcher cannot be started twice",
            )

        self.logger.info(
            "Starting configuration file watcher",
            watch_path=str(self.watch_path),
            debounce_seconds=self.debounce_seconds,
        )

        # Verify the file exists before starting
        if not self.watch_path.exists():
            raise SuperegoError(
                ErrorCode.INVALID_CONFIGURATION,
                f"Configuration file not found: {self.watch_path}",
                "Cannot monitor non-existent configuration file",
            )

        self._watcher_task = asyncio.create_task(self._watch_loop())

    async def stop(self) -> None:
        """Stop watching and cleanup resources."""
        self.logger.info("Stopping configuration file watcher")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel pending reload task
        if self._pending_reload_task and not self._pending_reload_task.done():
            self._pending_reload_task.cancel()
            try:
                await self._pending_reload_task
            except asyncio.CancelledError:
                pass

        # Cancel and wait for watcher task
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
            self._watcher_task = None

        self.logger.info("Configuration file watcher stopped")

    async def _watch_loop(self) -> None:
        """Main watch loop that monitors file changes."""
        try:
            # Watch the parent directory to catch file replacements
            watch_dir = self.watch_path.parent
            filename = self.watch_path.name

            self.logger.debug(
                "Starting file system watch",
                watch_dir=str(watch_dir),
                filename=filename,
            )

            async for changes in awatch(watch_dir, stop_event=self._shutdown_event):
                # Filter changes to only our target file
                relevant_changes = [
                    change for change in changes if Path(change[1]).name == filename
                ]

                if not relevant_changes:
                    continue

                self.logger.debug(
                    "Configuration file change detected",
                    changes=[
                        (change[0].name, change[1]) for change in relevant_changes
                    ],
                )

                # Schedule debounced reload
                await self._schedule_debounced_reload()

        except asyncio.CancelledError:
            self.logger.debug("File watcher cancelled")
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error in file watcher",
                error=str(e),
                exc_info=True,
            )
            # Don't re-raise - let the watcher restart if needed

    async def _schedule_debounced_reload(self) -> None:
        """Schedule a debounced reload, cancelling any pending reload."""
        # Cancel any pending reload
        if self._pending_reload_task and not self._pending_reload_task.done():
            self._pending_reload_task.cancel()
            try:
                await self._pending_reload_task
            except asyncio.CancelledError:
                pass

        # Schedule new debounced reload
        self._pending_reload_task = asyncio.create_task(self._debounced_reload())

    async def _debounced_reload(self) -> None:
        """Execute reload with debouncing to handle rapid file changes."""
        try:
            # Wait for debounce period
            await asyncio.sleep(self.debounce_seconds)

            # Check if file still exists after debounce
            if not self.watch_path.exists():
                self.logger.warning(
                    "Configuration file disappeared during debounce period",
                    watch_path=str(self.watch_path),
                )
                return

            # Record reload time
            current_time = asyncio.get_event_loop().time()
            self._last_reload_time = current_time

            self.logger.info(
                "Executing configuration reload",
                watch_path=str(self.watch_path),
            )

            # Execute the reload callback
            await self.reload_callback()

            self.logger.info(
                "Configuration reload completed successfully",
                reload_time=current_time,
            )

        except asyncio.CancelledError:
            self.logger.debug("Debounced reload cancelled")
            raise
        except Exception as e:
            self.logger.error(
                "Configuration reload failed",
                error=str(e),
                watch_path=str(self.watch_path),
                exc_info=True,
            )
            # Don't re-raise - log the error and continue watching

    def health_check(self) -> dict[str, Any]:
        """Provide health status for monitoring."""
        is_running = self._watcher_task is not None and not self._watcher_task.done()
        last_reload_age = (
            asyncio.get_event_loop().time() - self._last_reload_time
            if self._last_reload_time > 0
            else None
        )

        return {
            "status": "healthy" if is_running else "unhealthy",
            "message": "File watcher active"
            if is_running
            else "File watcher not running",
            "is_running": is_running,
            "watch_path": str(self.watch_path),
            "last_reload_time": self._last_reload_time
            if self._last_reload_time > 0
            else None,
            "last_reload_age_seconds": last_reload_age,
            "debounce_seconds": self.debounce_seconds,
        }

    async def trigger_reload(self) -> None:
        """Manually trigger a configuration reload for testing purposes."""
        self.logger.info("Manual configuration reload triggered")
        await self._schedule_debounced_reload()
