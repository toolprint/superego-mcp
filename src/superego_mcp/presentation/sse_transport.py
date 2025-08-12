"""Server-Sent Events (SSE) transport implementation for Superego MCP Server."""

import asyncio
import json
from typing import Any, Dict, Set

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastmcp import FastMCP
from pydantic import BaseModel
from uvicorn import Config, Server

from ..domain.models import Decision, ToolRequest
from ..domain.security_policy import SecurityPolicyEngine
from ..infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor

logger = structlog.get_logger(__name__)


class SSEEvent(BaseModel):
    """Server-Sent Event structure."""

    id: str | None = None
    event: str | None = None
    data: str
    retry: int | None = None


class SSEManager:
    """Manages Server-Sent Event streams."""

    def __init__(self, keepalive_interval: int = 30):
        """Initialize SSE manager.

        Args:
            keepalive_interval: Interval in seconds for keepalive messages
        """
        self.keepalive_interval = keepalive_interval
        self.subscribers: Dict[str, Set[asyncio.Queue]] = {
            "config": set(),
            "health": set(),
            "audit": set(),
        }
        self.keepalive_task = None

    async def subscribe(self, event_type: str) -> asyncio.Queue:
        """Subscribe to an event type.

        Args:
            event_type: Type of events to subscribe to

        Returns:
            Queue for receiving events
        """
        if event_type not in self.subscribers:
            raise ValueError(f"Unknown event type: {event_type}")

        queue = asyncio.Queue()
        self.subscribers[event_type].add(queue)

        logger.info(
            "SSE client subscribed",
            event_type=event_type,
            total_subscribers=len(self.subscribers[event_type]),
        )

        return queue

    def unsubscribe(self, event_type: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Type of events to unsubscribe from
            queue: Queue to unsubscribe
        """
        if event_type in self.subscribers:
            self.subscribers[event_type].discard(queue)
            logger.info(
                "SSE client unsubscribed",
                event_type=event_type,
                total_subscribers=len(self.subscribers[event_type]),
            )

    async def broadcast(self, event_type: str, event: SSEEvent) -> None:
        """Broadcast an event to all subscribers.

        Args:
            event_type: Type of event to broadcast
            event: Event to broadcast
        """
        if event_type not in self.subscribers:
            return

        # Remove closed queues
        closed_queues = set()

        for queue in self.subscribers[event_type].copy():
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Queue is full, mark for removal
                closed_queues.add(queue)
            except Exception as e:
                logger.error("Failed to broadcast SSE event", error=str(e))
                closed_queues.add(queue)

        # Clean up closed queues
        for queue in closed_queues:
            self.subscribers[event_type].discard(queue)

    async def start_keepalive(self) -> None:
        """Start keepalive task."""
        self.keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def stop_keepalive(self) -> None:
        """Stop keepalive task."""
        if self.keepalive_task:
            self.keepalive_task.cancel()
            try:
                await self.keepalive_task
            except asyncio.CancelledError:
                pass

    async def _keepalive_loop(self) -> None:
        """Send periodic keepalive messages."""
        while True:
            try:
                keepalive_event = SSEEvent(
                    event="keepalive",
                    data=json.dumps(
                        {"timestamp": str(asyncio.get_event_loop().time())}
                    ),
                )

                # Broadcast keepalive to all event types
                for event_type in self.subscribers:
                    await self.broadcast(event_type, keepalive_event)

                await asyncio.sleep(self.keepalive_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Keepalive error", error=str(e))


class SSETransport:
    """Server-Sent Events transport for streaming updates."""

    def __init__(
        self,
        mcp: FastMCP,
        security_policy: SecurityPolicyEngine,
        audit_logger: AuditLogger,
        error_handler: ErrorHandler,
        health_monitor: HealthMonitor,
        config: dict[str, Any],
    ):
        """Initialize SSE transport.

        Args:
            mcp: FastMCP application instance
            security_policy: Security policy engine
            audit_logger: Audit logger instance
            error_handler: Error handler instance
            health_monitor: Health monitor instance
            config: SSE transport configuration
        """
        self.mcp = mcp
        self.security_policy = security_policy
        self.audit_logger = audit_logger
        self.error_handler = error_handler
        self.health_monitor = health_monitor
        self.config = config

        # SSE manager
        keepalive_interval = config.get("keepalive_interval", 30)
        self.sse_manager = SSEManager(keepalive_interval)

        # Create FastAPI app for SSE
        self.app = FastAPI(
            title="Superego MCP SSE",
            description="Server-Sent Events transport for Superego MCP Server",
            version="0.1.0",
        )

        # Add CORS middleware
        cors_origins = config.get("cors_origins", ["*"])
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET"],
            allow_headers=["*"],
        )

        # Server instance
        self.server = None

        # Background tasks
        self.monitoring_tasks = []

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up SSE routes."""

        @self.app.get("/v1/events/config")
        async def config_events(request: Request):
            """Stream configuration change events.

            Returns:
                StreamingResponse with configuration events
            """
            return await self._create_event_stream("config", request)

        @self.app.get("/v1/events/health")
        async def health_events(request: Request):
            """Stream health status events.

            Returns:
                StreamingResponse with health events
            """
            return await self._create_event_stream("health", request)

        @self.app.get("/v1/events/audit")
        async def audit_events(request: Request):
            """Stream audit entry events.

            Returns:
                StreamingResponse with audit events
            """
            return await self._create_event_stream("audit", request)

        @self.app.get("/v1/events")
        async def all_events(request: Request):
            """Stream all events (combined).

            Returns:
                StreamingResponse with all event types
            """
            return await self._create_combined_event_stream(request)

    async def _create_event_stream(
        self, event_type: str, request: Request
    ) -> StreamingResponse:
        """Create an SSE stream for a specific event type.

        Args:
            event_type: Type of events to stream
            request: FastAPI request object

        Returns:
            StreamingResponse with SSE stream
        """

        async def event_generator():
            queue = await self.sse_manager.subscribe(event_type)

            try:
                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        break

                    try:
                        # Wait for event with timeout
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)

                        # Format SSE message
                        yield self._format_sse_message(event)

                    except asyncio.TimeoutError:
                        # Send periodic heartbeat
                        heartbeat = SSEEvent(
                            event="heartbeat",
                            data=json.dumps(
                                {"timestamp": str(asyncio.get_event_loop().time())}
                            ),
                        )
                        yield self._format_sse_message(heartbeat)

            except asyncio.CancelledError:
                pass
            finally:
                self.sse_manager.unsubscribe(event_type, queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    async def _create_combined_event_stream(
        self, request: Request
    ) -> StreamingResponse:
        """Create an SSE stream for all event types.

        Args:
            request: FastAPI request object

        Returns:
            StreamingResponse with combined SSE stream
        """

        async def event_generator():
            # Subscribe to all event types
            queues = {}
            for event_type in self.sse_manager.subscribers:
                queues[event_type] = await self.sse_manager.subscribe(event_type)

            try:
                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        break

                    # Wait for events from any queue
                    done, pending = await asyncio.wait(
                        [asyncio.create_task(queue.get()) for queue in queues.values()],
                        timeout=1.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if done:
                        # Process completed events
                        for task in done:
                            try:
                                event = task.result()
                                yield self._format_sse_message(event)
                            except Exception as e:
                                logger.error("Error processing SSE event", error=str(e))

                        # Cancel pending tasks
                        for task in pending:
                            task.cancel()
                    else:
                        # Send heartbeat on timeout
                        heartbeat = SSEEvent(
                            event="heartbeat",
                            data=json.dumps(
                                {"timestamp": str(asyncio.get_event_loop().time())}
                            ),
                        )
                        yield self._format_sse_message(heartbeat)

            except asyncio.CancelledError:
                pass
            finally:
                # Unsubscribe from all queues
                for event_type, queue in queues.items():
                    self.sse_manager.unsubscribe(event_type, queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    def _format_sse_message(self, event: SSEEvent) -> str:
        """Format an SSE event message.

        Args:
            event: Event to format

        Returns:
            Formatted SSE message string
        """
        lines = []

        if event.id:
            lines.append(f"id: {event.id}")
        if event.event:
            lines.append(f"event: {event.event}")
        if event.retry:
            lines.append(f"retry: {event.retry}")

        # Split data into multiple lines if needed
        for line in event.data.splitlines():
            lines.append(f"data: {line}")

        # Add empty line to indicate end of event
        lines.append("")

        return "\n".join(lines) + "\n"

    async def _start_monitoring_tasks(self) -> None:
        """Start background monitoring tasks."""
        # Start health monitoring
        health_task = asyncio.create_task(self._health_monitoring_loop())
        self.monitoring_tasks.append(health_task)

        # Start audit monitoring
        audit_task = asyncio.create_task(self._audit_monitoring_loop())
        self.monitoring_tasks.append(audit_task)

        # Start config monitoring
        config_task = asyncio.create_task(self._config_monitoring_loop())
        self.monitoring_tasks.append(config_task)

    async def _health_monitoring_loop(self) -> None:
        """Monitor health status and broadcast changes."""
        last_status = None

        while True:
            try:
                health_status = await self.health_monitor.check_health()
                current_status = health_status.model_dump()

                # Broadcast if status changed or every 5 minutes
                if current_status != last_status:
                    event = SSEEvent(
                        event="health_status",
                        data=json.dumps(
                            {
                                "timestamp": str(asyncio.get_event_loop().time()),
                                "status": current_status,
                            }
                        ),
                    )
                    await self.sse_manager.broadcast("health", event)
                    last_status = current_status

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health monitoring error", error=str(e))
                await asyncio.sleep(30)

    async def _audit_monitoring_loop(self) -> None:
        """Monitor for new audit entries and broadcast them."""
        last_entry_count = 0

        while True:
            try:
                stats = self.audit_logger.get_stats()
                current_count = stats.get("total_entries", 0)

                if current_count > last_entry_count:
                    # Get recent entries
                    recent_entries = self.audit_logger.get_recent_entries(
                        limit=current_count - last_entry_count
                    )

                    for entry in recent_entries:
                        event = SSEEvent(
                            event="audit_entry",
                            data=json.dumps(
                                {
                                    "timestamp": str(asyncio.get_event_loop().time()),
                                    "entry": entry.model_dump(mode="json"),
                                }
                            ),
                        )
                        await self.sse_manager.broadcast("audit", event)

                    last_entry_count = current_count

                await asyncio.sleep(5)  # Check every 5 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Audit monitoring error", error=str(e))
                await asyncio.sleep(5)

    async def _config_monitoring_loop(self) -> None:
        """Monitor configuration changes and broadcast them."""
        last_modified = None

        while True:
            try:
                if self.security_policy.rules_file.exists():
                    current_modified = self.security_policy.rules_file.stat().st_mtime

                    if current_modified != last_modified:
                        event = SSEEvent(
                            event="config_change",
                            data=json.dumps(
                                {
                                    "timestamp": str(asyncio.get_event_loop().time()),
                                    "rules_count": len(self.security_policy.rules),
                                    "last_modified": current_modified,
                                }
                            ),
                        )
                        await self.sse_manager.broadcast("config", event)
                        last_modified = current_modified

                await asyncio.sleep(10)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Config monitoring error", error=str(e))
                await asyncio.sleep(10)

    async def start(self) -> None:
        """Start the SSE server."""
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 8002)

        logger.info("Starting SSE transport", host=host, port=port)

        # Start SSE manager keepalive
        await self.sse_manager.start_keepalive()

        # Start monitoring tasks
        await self._start_monitoring_tasks()

        # Create uvicorn config
        config = Config(
            app=self.app,
            host=host,
            port=port,
            log_config=None,  # Use structlog instead
        )

        # Create server
        self.server = Server(config)

        try:
            await self.server.serve()
        except Exception as e:
            logger.error("SSE transport failed", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the SSE server gracefully."""
        logger.info("Stopping SSE transport")

        try:
            # Cancel and wait for monitoring tasks
            for task in self.monitoring_tasks:
                if not task.done():
                    task.cancel()

            # Wait for all monitoring tasks to complete
            if self.monitoring_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self.monitoring_tasks, return_exceptions=True),
                        timeout=3.0,
                    )
                except asyncio.TimeoutError:
                    logger.warning("Some monitoring tasks did not stop within timeout")
                except Exception as e:
                    logger.debug("Error stopping monitoring tasks", error=str(e))

            self.monitoring_tasks.clear()

            # Stop keepalive with timeout
            try:
                await asyncio.wait_for(self.sse_manager.stop_keepalive(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("SSE keepalive stop timed out")
            except Exception as e:
                logger.warning("Error stopping SSE keepalive", error=str(e))

            # Stop server
            if self.server:
                self.server.should_exit = True
                # Give server more time for graceful shutdown
                try:
                    await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            logger.error("Error during SSE transport shutdown", error=str(e))
        finally:
            logger.info("SSE transport stopped")

    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance.

        Returns:
            FastAPI application instance
        """
        return self.app
