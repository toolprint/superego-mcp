"""WebSocket transport implementation for Superego MCP Server."""

import asyncio
import json
from typing import Any, Dict, Set

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from pydantic import BaseModel, ValidationError
from uvicorn import Config, Server

from ..domain.models import Decision, ToolRequest
from ..domain.security_policy import SecurityPolicyEngine
from ..infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor

logger = structlog.get_logger(__name__)


class WSMessage(BaseModel):
    """WebSocket message structure."""

    message_id: str
    type: str  # "evaluate", "health", "subscribe", "unsubscribe"
    data: dict[str, Any]


class WSResponse(BaseModel):
    """WebSocket response structure."""

    message_id: str
    type: str  # "response", "notification", "error"
    data: dict[str, Any]
    error: str | None = None


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[str, Set[WebSocket]] = {
            "health": set(),
            "audit": set(),
            "config": set(),
        }

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(
            "WebSocket client connected", total_connections=len(self.active_connections)
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)

        # Remove from all subscriptions
        for subscription_set in self.subscriptions.values():
            subscription_set.discard(websocket)

        logger.info(
            "WebSocket client disconnected",
            total_connections=len(self.active_connections),
        )

    async def send_personal_message(
        self, message: WSResponse, websocket: WebSocket
    ) -> None:
        """Send a message to a specific client."""
        try:
            await websocket.send_text(message.model_dump_json())
        except Exception as e:
            logger.error("Failed to send WebSocket message", error=str(e))
            self.disconnect(websocket)

    async def broadcast_to_subscribers(
        self, subscription_type: str, message: WSResponse
    ) -> None:
        """Broadcast a message to all subscribers of a specific type."""
        if subscription_type not in self.subscriptions:
            return

        disconnected = set()
        for websocket in self.subscriptions[subscription_type].copy():
            try:
                await websocket.send_text(message.model_dump_json())
            except Exception as e:
                logger.error("Failed to broadcast to WebSocket client", error=str(e))
                disconnected.add(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)

    def subscribe(self, websocket: WebSocket, subscription_type: str) -> bool:
        """Subscribe a client to a specific notification type."""
        if subscription_type not in self.subscriptions:
            return False

        self.subscriptions[subscription_type].add(websocket)
        return True

    def unsubscribe(self, websocket: WebSocket, subscription_type: str) -> bool:
        """Unsubscribe a client from a specific notification type."""
        if subscription_type not in self.subscriptions:
            return False

        self.subscriptions[subscription_type].discard(websocket)
        return True


class WebSocketTransport:
    """WebSocket transport for real-time MCP communication."""

    def __init__(
        self,
        mcp: FastMCP,
        security_policy: SecurityPolicyEngine,
        audit_logger: AuditLogger,
        error_handler: ErrorHandler,
        health_monitor: HealthMonitor,
        config: dict[str, Any],
    ):
        """Initialize WebSocket transport.

        Args:
            mcp: FastMCP application instance
            security_policy: Security policy engine
            audit_logger: Audit logger instance
            error_handler: Error handler instance
            health_monitor: Health monitor instance
            config: WebSocket transport configuration
        """
        self.mcp = mcp
        self.security_policy = security_policy
        self.audit_logger = audit_logger
        self.error_handler = error_handler
        self.health_monitor = health_monitor
        self.config = config

        # Connection manager
        self.connection_manager = ConnectionManager()

        # Create FastAPI app for WebSocket
        self.app = FastAPI(
            title="Superego MCP WebSocket",
            description="WebSocket transport for Superego MCP Server",
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
        self.heartbeat_task = None

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up WebSocket routes."""

        @self.app.websocket("/v1/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Main WebSocket endpoint for MCP communication."""
            await self.connection_manager.connect(websocket)

            try:
                while True:
                    # Receive message from client
                    text_data = await websocket.receive_text()

                    try:
                        # Parse message
                        message_data = json.loads(text_data)
                        message = WSMessage(**message_data)

                        # Handle message
                        response = await self._handle_message(message, websocket)

                        # Send response
                        if response:
                            await self.connection_manager.send_personal_message(
                                response, websocket
                            )

                    except ValidationError as e:
                        # Send error response for invalid message format
                        error_response = WSResponse(
                            message_id="unknown",
                            type="error",
                            data={},
                            error=f"Invalid message format: {str(e)}",
                        )
                        await self.connection_manager.send_personal_message(
                            error_response, websocket
                        )

                    except json.JSONDecodeError:
                        # Send error response for invalid JSON
                        error_response = WSResponse(
                            message_id="unknown",
                            type="error",
                            data={},
                            error="Invalid JSON format",
                        )
                        await self.connection_manager.send_personal_message(
                            error_response, websocket
                        )

            except WebSocketDisconnect:
                self.connection_manager.disconnect(websocket)
            except Exception as e:
                logger.error("WebSocket connection error", error=str(e))
                self.connection_manager.disconnect(websocket)

    async def _handle_message(
        self, message: WSMessage, websocket: WebSocket
    ) -> WSResponse | None:
        """Handle incoming WebSocket message.

        Args:
            message: Parsed WebSocket message
            websocket: WebSocket connection

        Returns:
            Response message or None for notifications
        """
        try:
            if message.type == "evaluate":
                return await self._handle_evaluate(message, websocket)
            elif message.type == "health":
                return await self._handle_health_check(message, websocket)
            elif message.type == "subscribe":
                return await self._handle_subscribe(message, websocket)
            elif message.type == "unsubscribe":
                return await self._handle_unsubscribe(message, websocket)
            elif message.type == "ping":
                return await self._handle_ping(message, websocket)
            else:
                return WSResponse(
                    message_id=message.message_id,
                    type="error",
                    data={},
                    error=f"Unknown message type: {message.type}",
                )

        except Exception as e:
            logger.error(
                "Error handling WebSocket message",
                error=str(e),
                message_type=message.type,
            )
            return WSResponse(
                message_id=message.message_id,
                type="error",
                data={},
                error=str(e),
            )

    async def _handle_evaluate(
        self, message: WSMessage, websocket: WebSocket
    ) -> WSResponse:
        """Handle tool evaluation request."""
        try:
            data = message.data
            tool_request = ToolRequest(
                tool_name=data["tool_name"],
                parameters=data.get("parameters", {}),
                agent_id=data["agent_id"],
                session_id=data["session_id"],
                cwd=data.get("cwd", "/tmp"),
            )

            logger.info(
                "WebSocket: Evaluating tool request",
                tool_name=tool_request.tool_name,
                agent_id=tool_request.agent_id,
                session_id=tool_request.session_id,
            )

            decision = await self.security_policy.evaluate(tool_request)

            # Log decision to audit trail
            rule_matches = [decision.rule_id] if decision.rule_id else []
            await self.audit_logger.log_decision(tool_request, decision, rule_matches)

            # Notify audit subscribers
            await self._notify_audit_subscribers(tool_request, decision)

            return WSResponse(
                message_id=message.message_id,
                type="response",
                data=decision.model_dump(),
            )

        except KeyError as e:
            return WSResponse(
                message_id=message.message_id,
                type="error",
                data={},
                error=f"Missing required field: {str(e)}",
            )
        except Exception as e:
            # Handle errors with centralized error handler
            fallback_decision = self.error_handler.handle_error(e, tool_request)

            # Log fallback decision
            await self.audit_logger.log_decision(tool_request, fallback_decision, [])

            return WSResponse(
                message_id=message.message_id,
                type="response",
                data=fallback_decision.model_dump(),
            )

    async def _handle_health_check(
        self, message: WSMessage, websocket: WebSocket
    ) -> WSResponse:
        """Handle health check request."""
        try:
            health_status = await self.health_monitor.check_health()
            return WSResponse(
                message_id=message.message_id,
                type="response",
                data=health_status.model_dump(),
            )
        except Exception as e:
            return WSResponse(
                message_id=message.message_id,
                type="error",
                data={},
                error=str(e),
            )

    async def _handle_subscribe(
        self, message: WSMessage, websocket: WebSocket
    ) -> WSResponse:
        """Handle subscription request."""
        subscription_type = message.data.get("subscription_type")

        if not subscription_type:
            return WSResponse(
                message_id=message.message_id,
                type="error",
                data={},
                error="Missing subscription_type",
            )

        success = self.connection_manager.subscribe(websocket, subscription_type)

        return WSResponse(
            message_id=message.message_id,
            type="response",
            data={
                "subscribed": success,
                "subscription_type": subscription_type,
            },
        )

    async def _handle_unsubscribe(
        self, message: WSMessage, websocket: WebSocket
    ) -> WSResponse:
        """Handle unsubscription request."""
        subscription_type = message.data.get("subscription_type")

        if not subscription_type:
            return WSResponse(
                message_id=message.message_id,
                type="error",
                data={},
                error="Missing subscription_type",
            )

        success = self.connection_manager.unsubscribe(websocket, subscription_type)

        return WSResponse(
            message_id=message.message_id,
            type="response",
            data={
                "unsubscribed": success,
                "subscription_type": subscription_type,
            },
        )

    async def _handle_ping(
        self, message: WSMessage, websocket: WebSocket
    ) -> WSResponse:
        """Handle ping request."""
        return WSResponse(
            message_id=message.message_id,
            type="response",
            data={"pong": True, "timestamp": str(asyncio.get_event_loop().time())},
        )

    async def _notify_audit_subscribers(
        self, tool_request: ToolRequest, decision: Decision
    ) -> None:
        """Notify audit subscribers of new decision."""
        notification = WSResponse(
            message_id="audit_notification",
            type="notification",
            data={
                "event_type": "audit",
                "tool_request": tool_request.model_dump(),
                "decision": decision.model_dump(),
                "timestamp": str(asyncio.get_event_loop().time()),
            },
        )

        await self.connection_manager.broadcast_to_subscribers("audit", notification)

    async def _start_heartbeat(self) -> None:
        """Start heartbeat task to keep connections alive."""
        while True:
            try:
                # Send heartbeat to all connections every 30 seconds
                heartbeat = WSResponse(
                    message_id="heartbeat",
                    type="notification",
                    data={
                        "heartbeat": True,
                        "timestamp": str(asyncio.get_event_loop().time()),
                    },
                )

                for websocket in self.connection_manager.active_connections.copy():
                    try:
                        await websocket.send_text(heartbeat.model_dump_json())
                    except Exception:
                        self.connection_manager.disconnect(websocket)

                await asyncio.sleep(30)  # 30 second heartbeat

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error", error=str(e))

    async def start(self) -> None:
        """Start the WebSocket server."""
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 8001)

        logger.info("Starting WebSocket transport", host=host, port=port)

        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self._start_heartbeat())

        # Create uvicorn config
        config = Config(
            app=self.app,
            host=host,
            port=port,
            log_config=None,  # Use structlog instead
            ws_ping_interval=20,  # Enable WebSocket ping
            ws_ping_timeout=30,
        )

        # Create server
        self.server = Server(config)

        try:
            await self.server.serve()
        except Exception as e:
            logger.error("WebSocket transport failed", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the WebSocket server gracefully."""
        logger.info("Stopping WebSocket transport")

        try:
            # Cancel and wait for heartbeat task
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
                try:
                    await asyncio.wait_for(self.heartbeat_task, timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    logger.debug("Heartbeat task cancelled successfully")
                except Exception as e:
                    logger.warning("Error stopping heartbeat task", error=str(e))

            # Stop server
            if self.server:
                self.server.should_exit = True
                # Give server more time for graceful shutdown
                try:
                    await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    pass

            # Close all active connections
            for websocket in self.connection_manager.active_connections.copy():
                try:
                    await websocket.close()
                except Exception as e:
                    logger.debug("Error closing WebSocket connection", error=str(e))

            self.connection_manager.active_connections.clear()
            for subscription_set in self.connection_manager.subscriptions.values():
                subscription_set.clear()

        except Exception as e:
            logger.error("Error during WebSocket transport shutdown", error=str(e))
        finally:
            logger.info("WebSocket transport stopped")

    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance.

        Returns:
            FastAPI application instance
        """
        return self.app
