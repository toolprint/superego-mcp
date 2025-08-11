"""Configuration management for Superego MCP Server."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


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
