"""Configuration management for Superego MCP Server."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ..infrastructure.ai_service import SamplingConfig


class TransportConfig(BaseModel):
    """Individual transport configuration."""

    enabled: bool = Field(default=False, description="Enable this transport")
    host: str = Field(default="0.0.0.0", description="Transport host address")
    port: int = Field(description="Transport port")
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")


class HTTPTransportConfig(TransportConfig):
    """HTTP transport configuration."""

    port: int = Field(default=8000, description="HTTP server port")


class WebSocketTransportConfig(TransportConfig):
    """WebSocket transport configuration."""

    port: int = Field(default=8001, description="WebSocket server port")
    ping_interval: int = Field(
        default=20, description="WebSocket ping interval in seconds"
    )
    ping_timeout: int = Field(
        default=30, description="WebSocket ping timeout in seconds"
    )


class SSETransportConfig(TransportConfig):
    """Server-Sent Events transport configuration."""

    port: int = Field(default=8002, description="SSE server port")
    keepalive_interval: int = Field(
        default=30, description="Keepalive interval in seconds"
    )


class MultiTransportConfig(BaseModel):
    """Multi-transport configuration."""

    stdio: dict[str, Any] = Field(
        default_factory=dict, description="STDIO transport config (always enabled)"
    )
    http: HTTPTransportConfig = Field(
        default_factory=HTTPTransportConfig, description="HTTP transport config"
    )
    websocket: WebSocketTransportConfig = Field(
        default_factory=WebSocketTransportConfig,
        description="WebSocket transport config",
    )
    sse: SSETransportConfig = Field(
        default_factory=SSETransportConfig, description="SSE transport config"
    )


class RequestQueueConfig(BaseModel):
    """Request queue configuration."""

    max_size: int = Field(default=1000, description="Maximum queue size")
    timeout_seconds: int = Field(default=30, description="Request timeout in seconds")
    ai_sampling_concurrency: int = Field(
        default=10, description="Concurrent AI sampling requests"
    )
    enable_backpressure: bool = Field(
        default=True, description="Enable backpressure handling"
    )


class ConnectionPoolingConfig(BaseModel):
    """Connection pooling configuration."""

    max_connections: int = Field(default=100, description="Maximum total connections")
    max_keepalive_connections: int = Field(
        default=20, description="Maximum keepalive connections"
    )
    keepalive_timeout: int = Field(
        default=30, description="Keepalive timeout in seconds"
    )


class CachingConfig(BaseModel):
    """Caching configuration."""

    response_cache_ttl: int = Field(
        default=300, description="Response cache TTL in seconds"
    )
    pattern_cache_size: int = Field(default=1000, description="Pattern cache size")
    enable_compression: bool = Field(
        default=True, description="Enable cache compression"
    )


class MemoryConfig(BaseModel):
    """Memory optimization configuration."""

    object_pool_size: int = Field(default=100, description="Object pool size")
    intern_strings: bool = Field(default=True, description="Enable string interning")


class BatchingConfig(BaseModel):
    """Request batching configuration."""

    enabled: bool = Field(default=True, description="Enable request batching")
    batch_size: int = Field(default=10, description="Maximum batch size")
    batch_timeout: float = Field(default=0.5, description="Batch timeout in seconds")


class PerformanceConfig(BaseModel):
    """Performance optimization configuration."""

    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9090, description="Metrics endpoint port")
    request_queue: RequestQueueConfig = Field(
        default_factory=RequestQueueConfig, description="Request queue config"
    )
    connection_pooling: ConnectionPoolingConfig = Field(
        default_factory=ConnectionPoolingConfig, description="Connection pooling config"
    )
    caching: CachingConfig = Field(
        default_factory=CachingConfig, description="Caching config"
    )
    memory: MemoryConfig = Field(
        default_factory=MemoryConfig, description="Memory optimization config"
    )
    batching: BatchingConfig = Field(
        default_factory=BatchingConfig, description="Request batching config"
    )


class ServerConfig(BaseModel):
    """Server configuration model."""

    host: str = Field(default="localhost", description="Server host address")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    rules_file: str = Field(
        default="config/rules.yaml", description="Path to rules file"
    )
    hot_reload: bool = Field(default=True, description="Enable hot reload of rules")

    # Health check settings
    health_check_enabled: bool = Field(default=True, description="Enable health checks")
    health_check_interval: int = Field(
        default=30, description="Health check interval in seconds"
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(default=False, description="Enable rate limiting")
    rate_limit_requests: int = Field(
        default=100, description="Requests per minute limit"
    )

    # AI Sampling configuration
    ai_sampling: SamplingConfig = Field(
        default_factory=SamplingConfig, description="AI sampling configuration"
    )

    # Multi-transport configuration
    transport: MultiTransportConfig = Field(
        default_factory=MultiTransportConfig,
        description="Multi-transport configuration",
    )

    # Performance optimization configuration
    performance: PerformanceConfig = Field(
        default_factory=PerformanceConfig,
        description="Performance optimization configuration",
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "SUPEREGO_"


class ConfigManager:
    """Manager for loading and managing server configuration."""

    def __init__(self, config_file: str | None = None):
        """Initialize the config manager.

        Args:
            config_file: Optional path to configuration file
        """
        self.config_file = config_file or "config/server.yaml"
        self._config: ServerConfig | None = None

    def load_config(self) -> ServerConfig:
        """Load configuration from file and environment variables.

        Returns:
            ServerConfig instance with loaded configuration
        """
        config_data: dict[str, Any] = {}

        # Load from YAML file if it exists
        config_path = Path(self.config_file)
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}

        # Create config object (Pydantic will handle env vars automatically)
        self._config = ServerConfig(**config_data)
        return self._config

    def get_config(self) -> ServerConfig:
        """Get the current configuration.

        Returns:
            ServerConfig instance
        """
        if self._config is None:
            return self.load_config()
        return self._config

    def reload_config(self) -> ServerConfig:
        """Reload configuration from file.

        Returns:
            Updated ServerConfig instance
        """
        return self.load_config()

    def save_default_config(self) -> None:
        """Save a default configuration file."""
        config_path = Path(self.config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        default_config = ServerConfig()
        config_data = default_config.model_dump()

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f, default_flow_style=False, indent=2)
