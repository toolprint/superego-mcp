"""HTTP client for testing the Superego MCP Server.

This module provides an async HTTP client for testing various Superego MCP Server
endpoints including tool evaluation, Claude Code hooks, and health checks.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
import structlog
from pydantic import BaseModel, Field

from ..config.loader import TestHarnessConfig

logger = structlog.get_logger(__name__)


class ToolEvaluationRequest(BaseModel):
    """Request model for tool evaluation."""
    
    tool_name: str = Field(..., description="Name of the tool to evaluate")
    parameters: Dict[str, Any] = Field(..., description="Tool parameters")
    agent_id: str = Field(..., description="Agent identifier")
    session_id: str = Field(..., description="Session identifier")


class HookRequest(BaseModel):
    """Request model for Claude Code hook evaluation."""
    
    event_name: str = Field(..., description="Hook event name")
    tool_name: str = Field(..., description="Tool name")
    arguments: Dict[str, Any] = Field(..., description="Tool arguments")
    agent_id: str = Field(default="test-agent", description="Agent identifier")
    session_id: str = Field(default="test-session", description="Session identifier")


class SuperegoClientError(Exception):
    """Base exception for Superego client errors."""
    pass


class SuperegoTimeoutError(SuperegoClientError):
    """Raised when a request times out."""
    pass


class SuperegoConnectionError(SuperegoClientError):
    """Raised when connection to server fails."""
    pass


class SuperegoHTTPError(SuperegoClientError):
    """Raised when server returns an HTTP error."""
    
    def __init__(self, message: str, status_code: int, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class SuperegoTestClient:
    """Async HTTP client for testing the Superego MCP Server.
    
    This client provides methods for testing various server endpoints with
    comprehensive error handling, timeouts, and retry logic.
    """
    
    def __init__(self, config: TestHarnessConfig) -> None:
        """Initialize the Superego test client.
        
        Args:
            config: Test harness configuration containing server settings
        """
        self.config = config
        self.base_url = config.server.base_url.rstrip("/")
        self.timeout = config.client.timeout
        self.max_retries = config.server.max_retries
        self.retry_delay = config.server.retry_delay
        
        # Configure HTTP client with connection pooling and timeouts
        self._client_timeout = httpx.Timeout(
            connect=10.0,
            read=self.timeout,
            write=self.timeout,
            pool=self.timeout
        )
        self._client_limits = httpx.Limits(
            max_connections=config.client.pool_size,
            max_keepalive_connections=config.client.pool_size // 4,
            keepalive_expiry=config.client.keepalive_timeout
        )
        self._verify_ssl = config.client.verify_ssl
        self._http2 = config.client.http2
        
        # Add authentication headers if configured
        self._headers = self._build_auth_headers()
        
        self._client: Optional[httpx.AsyncClient] = None
        self._logger = logger.bind(base_url=self.base_url)
    
    def _build_auth_headers(self) -> Dict[str, str]:
        """Build authentication headers based on config.
        
        Returns:
            Dictionary of headers for authentication
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SuperegoTestClient/1.0",
        }
        
        auth_config = self.config.auth
        
        if auth_config.method == "bearer" and auth_config.bearer_token:
            headers["Authorization"] = f"Bearer {auth_config.bearer_token}"
        elif auth_config.method == "api_key" and auth_config.api_key:
            headers["X-API-Key"] = auth_config.api_key
        
        # Add custom headers
        headers.update(auth_config.headers)
        
        return headers
    
    async def __aenter__(self) -> "SuperegoTestClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=self._client_timeout,
                limits=self._client_limits,
                verify=self._verify_ssl,
                http2=self._http2
            )
    
    async def close(self) -> None:
        """Close the HTTP client and cleanup resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[float] = None,
    ) -> httpx.Response:
        """Make an HTTP request with error handling and retries.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data for POST/PUT requests
            params: URL query parameters
            timeout_override: Override default timeout for this request
            
        Returns:
            HTTP response object
            
        Raises:
            SuperegoTimeoutError: If request times out
            SuperegoConnectionError: If connection fails
            SuperegoHTTPError: If server returns an error status
        """
        await self._ensure_client()
        
        url = urljoin(self.base_url, endpoint.lstrip("/"))
        timeout = timeout_override or self.timeout
        
        # Update timeout for this specific request
        client_timeout = httpx.Timeout(
            connect=10.0,
            read=timeout,
            write=timeout,
            pool=timeout
        )
        
        request_logger = self._logger.bind(
            method=method,
            url=url,
            timeout=timeout
        )
        
        last_exception: Optional[SuperegoClientError] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                request_logger.debug(
                    "Making request",
                    attempt=attempt + 1,
                    max_attempts=self.max_retries + 1
                )
                
                start_time = time.perf_counter()
                
                assert self._client is not None, "HTTP client should be initialized"
                response = await self._client.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    timeout=client_timeout
                )
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                request_logger.debug(
                    "Request completed",
                    status_code=response.status_code,
                    elapsed_ms=round(elapsed_ms, 2)
                )
                
                # Check for HTTP errors
                if response.status_code >= 400:
                    error_text = ""
                    try:
                        error_text = response.text
                    except Exception:
                        pass
                    
                    raise SuperegoHTTPError(
                        f"HTTP {response.status_code} error for {method} {url}",
                        status_code=response.status_code,
                        response_text=error_text
                    )
                
                return response
                
            except httpx.TimeoutException as e:
                last_exception = SuperegoTimeoutError(
                    f"Request to {url} timed out after {timeout}s"
                )
                request_logger.warning(
                    "Request timeout",
                    attempt=attempt + 1,
                    timeout=timeout,
                    error=str(e)
                )
                
            except httpx.ConnectError as e:
                last_exception = SuperegoConnectionError(
                    f"Failed to connect to {url}: {e}"
                )
                request_logger.warning(
                    "Connection error",
                    attempt=attempt + 1,
                    error=str(e)
                )
                
            except SuperegoHTTPError:
                # Don't retry HTTP errors
                raise
                
            except Exception as e:
                last_exception = SuperegoClientError(f"Unexpected error: {e}")
                request_logger.error(
                    "Unexpected error",
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__
                )
            
            # Wait before retry (except on last attempt)
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        # All retries exhausted
        if last_exception:
            raise last_exception
        else:
            raise SuperegoClientError(f"All {self.max_retries + 1} attempts failed")
    
    async def evaluate_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        agent_id: str = "test-agent",
        session_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Evaluate a tool request for security concerns.
        
        Args:
            tool_name: Name of the tool to evaluate
            parameters: Tool parameters dictionary
            agent_id: Agent identifier for the request
            session_id: Session identifier (auto-generated if None)
            timeout: Request timeout override
            
        Returns:
            Evaluation decision and metadata
            
        Raises:
            SuperegoClientError: If the request fails
        """
        if session_id is None:
            session_id = f"{self.config.scenarios.session_prefix}-{int(time.time())}"
        
        request_data = ToolEvaluationRequest(
            tool_name=tool_name,
            parameters=parameters,
            agent_id=agent_id,
            session_id=session_id
        )
        
        self._logger.info(
            "Evaluating tool request",
            tool_name=tool_name,
            agent_id=agent_id,
            session_id=session_id
        )
        
        response = await self._make_request(
            method="POST",
            endpoint="/v1/evaluate",
            data=request_data.model_dump(),
            timeout_override=timeout
        )
        
        result = response.json()
        return result  # type: ignore[no-any-return]
    
    async def test_claude_hook(
        self,
        event_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_id: str = "test-agent",
        session_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Test a Claude Code hook evaluation.
        
        Args:
            event_name: Hook event name (e.g., "pre_tool_use")
            tool_name: Name of the tool being used
            arguments: Tool arguments dictionary
            agent_id: Agent identifier for the request
            session_id: Session identifier (auto-generated if None)
            timeout: Request timeout override
            
        Returns:
            Hook evaluation result
            
        Raises:
            SuperegoClientError: If the request fails
        """
        if session_id is None:
            session_id = f"{self.config.scenarios.session_prefix}-{int(time.time())}"
        
        # Build hook request compatible with Claude Code format
        hook_data = {
            "eventName": event_name,
            "toolName": tool_name,
            "arguments": arguments,
            "metadata": {
                "agentId": agent_id,
                "sessionId": session_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        self._logger.info(
            "Testing Claude Code hook",
            event_name=event_name,
            tool_name=tool_name,
            agent_id=agent_id,
            session_id=session_id
        )
        
        response = await self._make_request(
            method="POST",
            endpoint="/v1/hooks",
            data=hook_data,
            timeout_override=timeout
        )
        
        result = response.json()
        return result  # type: ignore[no-any-return]
    
    async def check_health(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Check the health status of the Superego server.
        
        Args:
            timeout: Request timeout override (defaults to 10 seconds for health checks)
            
        Returns:
            Health status information
            
        Raises:
            SuperegoClientError: If the health check fails
        """
        # Use shorter timeout for health checks if not specified
        health_timeout = timeout or 10.0
        
        self._logger.debug("Checking server health")
        
        response = await self._make_request(
            method="GET",
            endpoint="/v1/health",
            timeout_override=health_timeout
        )
        
        health_data = response.json()
        
        self._logger.info(
            "Health check completed",
            status=health_data.get("status"),
            version=health_data.get("version")
        )
        
        return health_data  # type: ignore[no-any-return]
    
    async def get_server_info(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get server configuration and status information.
        
        Args:
            timeout: Request timeout override
            
        Returns:
            Server information dictionary
            
        Raises:
            SuperegoClientError: If the request fails
        """
        self._logger.debug("Getting server info")
        
        response = await self._make_request(
            method="GET",
            endpoint="/v1/server-info",
            timeout_override=timeout
        )
        
        result = response.json()
        return result  # type: ignore[no-any-return]
    
    async def get_current_rules(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get current security rules configuration.
        
        Args:
            timeout: Request timeout override
            
        Returns:
            Current rules configuration
            
        Raises:
            SuperegoClientError: If the request fails
        """
        self._logger.debug("Getting current rules")
        
        response = await self._make_request(
            method="GET",
            endpoint="/v1/config/rules",
            timeout_override=timeout
        )
        
        result = response.json()
        return result  # type: ignore[no-any-return]
    
    async def get_audit_entries(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get recent audit entries.
        
        Args:
            timeout: Request timeout override
            
        Returns:
            Recent audit entries and statistics
            
        Raises:
            SuperegoClientError: If the request fails
        """
        self._logger.debug("Getting recent audit entries")
        
        response = await self._make_request(
            method="GET",
            endpoint="/v1/audit/recent",
            timeout_override=timeout
        )
        
        result = response.json()
        return result  # type: ignore[no-any-return]
    
    async def get_metrics(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get performance metrics.
        
        Args:
            timeout: Request timeout override
            
        Returns:
            System performance metrics
            
        Raises:
            SuperegoClientError: If the request fails
        """
        self._logger.debug("Getting performance metrics")
        
        response = await self._make_request(
            method="GET",
            endpoint="/v1/metrics",
            timeout_override=timeout
        )
        
        result = response.json()
        return result  # type: ignore[no-any-return]