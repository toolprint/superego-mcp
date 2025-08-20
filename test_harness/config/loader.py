"""Configuration loading and management for the test harness."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from pydantic import BaseModel, Field, ValidationError


class ServerConfig(BaseModel):
    """Server connection configuration."""
    
    base_url: str = Field(default="http://localhost:8000", description="Base URL for the server")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    health_endpoint: str = Field(default="/health", description="Health check endpoint")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Delay between retries in seconds")


class ScenariosConfig(BaseModel):
    """Test scenarios configuration."""
    
    agent_id: str = Field(default="test-agent", description="Default agent identifier")
    session_prefix: str = Field(default="test-session", description="Session prefix for test isolation")
    cwd: str = Field(default=".", description="Current working directory for tests")
    scenario_timeout: int = Field(default=60, description="Default scenario timeout in seconds")
    max_concurrent: int = Field(default=5, description="Maximum concurrent scenarios")


class LoadTestingConfig(BaseModel):
    """Load testing configuration."""
    
    concurrent: int = Field(default=10, description="Number of concurrent connections")
    duration: int = Field(default=60, description="Test duration in seconds")
    ramp_up: int = Field(default=10, description="Ramp-up time in seconds")
    target_rps: int = Field(default=100, description="Target requests per second")
    max_response_time: int = Field(default=1000, description="Maximum response time threshold in ms")


class OutputConfig(BaseModel):
    """Output configuration."""
    
    format: str = Field(default="table", description="Output format: json, table, summary")
    colors: bool = Field(default=True, description="Enable colored output")
    verbose: bool = Field(default=False, description="Verbose output mode")
    save_results: bool = Field(default=False, description="Save results to file")
    results_file: str = Field(default="test_results.json", description="Results file path")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")
    format: str = Field(default="text", description="Log format: text, json")
    file: str = Field(default="", description="Log file path (empty for stdout only)")
    log_requests: bool = Field(default=False, description="Enable request/response logging")


class AuthConfig(BaseModel):
    """Authentication configuration."""
    
    method: str = Field(default="none", description="Authentication method: none, bearer, api_key")
    api_key: str = Field(default="", description="API key for authentication")
    bearer_token: str = Field(default="", description="Bearer token for authentication")
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom headers")


class ValidationConfig(BaseModel):
    """Response validation configuration."""
    
    enabled: bool = Field(default=True, description="Enable response schema validation")
    mode: str = Field(default="strict", description="Validation mode: strict, permissive")
    rules_file: str = Field(default="", description="Custom validation rules file path")


class ClientConfig(BaseModel):
    """HTTP client configuration."""
    
    timeout: int = Field(default=30, description="HTTP client timeout in seconds")
    pool_size: int = Field(default=100, description="Connection pool size")
    keepalive_timeout: int = Field(default=30, description="Keep-alive timeout in seconds")
    http2: bool = Field(default=False, description="Enable HTTP/2")
    verify_ssl: bool = Field(default=True, description="SSL verification")


class MetricsConfig(BaseModel):
    """Metrics collection configuration."""
    
    enabled: bool = Field(default=True, description="Enable metrics collection")
    export_format: str = Field(default="json", description="Metrics export format: prometheus, json")
    interval: int = Field(default=5, description="Metrics collection interval in seconds")
    custom_metrics: list[str] = Field(default_factory=list, description="Custom metrics to collect")


class EnvironmentConfig(BaseModel):
    """Environment configuration."""
    
    variables: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    type: str = Field(default="development", description="Environment type")
    data_dir: str = Field(default="test_data", description="Test data directory")
    cleanup: bool = Field(default=True, description="Cleanup after tests")


class TestHarnessConfig(BaseModel):
    """Complete test harness configuration."""
    
    server: ServerConfig = Field(default_factory=ServerConfig)
    scenarios: ScenariosConfig = Field(default_factory=ScenariosConfig)
    load_testing: LoadTestingConfig = Field(default_factory=LoadTestingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    client: ClientConfig = Field(default_factory=ClientConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)

    class Config:
        """Pydantic configuration."""
        env_prefix = "TEST_HARNESS_"


class ConfigLoader:
    """Configuration loader with TOML support and validation."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the config loader.
        
        Args:
            config_dir: Directory containing configuration files.
                       Defaults to test_harness/config relative to this file.
        """
        if config_dir is None:
            self.config_dir = Path(__file__).parent
        else:
            self.config_dir = Path(config_dir)
        
        self._config: Optional[TestHarnessConfig] = None

    def load_config(self, profile: str = "default") -> TestHarnessConfig:
        """Load configuration from TOML files with profile support.
        
        Args:
            profile: Configuration profile to load (e.g., 'default', 'dev', 'prod')
            
        Returns:
            Loaded and validated configuration
            
        Raises:
            FileNotFoundError: If required configuration files are missing
            ValidationError: If configuration validation fails
            ValueError: If TOML parsing fails
        """
        config_data: Dict[str, Any] = {}
        
        # Load default configuration first
        default_config_path = self.config_dir / "default.toml"
        if default_config_path.exists():
            config_data = self._load_toml_file(default_config_path)
        else:
            raise FileNotFoundError(
                f"Default configuration file not found: {default_config_path}"
            )
        
        # Load profile-specific overrides if different from default
        if profile != "default":
            profile_config_path = self.config_dir / f"{profile}.toml"
            if profile_config_path.exists():
                profile_data = self._load_toml_file(profile_config_path)
                config_data = self._merge_configs(config_data, profile_data)
        
        # Apply environment variable overrides
        config_data = self._apply_env_overrides(config_data)
        
        try:
            self._config = TestHarnessConfig(**config_data)
            return self._config
        except ValidationError as e:
            raise ValidationError(f"Configuration validation failed: {e}") from e

    def _load_toml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load and parse a TOML file.
        
        Args:
            file_path: Path to the TOML file
            
        Returns:
            Parsed TOML data as dictionary
            
        Raises:
            ValueError: If TOML parsing fails
        """
        try:
            with open(file_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse TOML file {file_path}: {e}") from e

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries.
        
        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary
            
        Returns:
            Merged configuration dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result

    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration.
        
        Environment variables follow the pattern: TEST_HARNESS_SECTION_KEY
        For nested keys: TEST_HARNESS_SECTION_SUBSECTION_KEY
        
        Args:
            config_data: Base configuration data
            
        Returns:
            Configuration data with environment overrides applied
        """
        result = config_data.copy()
        env_prefix = "TEST_HARNESS_"
        
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(env_prefix):
                continue
                
            # Remove prefix and convert to lowercase
            config_key = env_key[len(env_prefix):].lower()
            key_parts = config_key.split("_")
            
            # Navigate to the correct nested dictionary
            current_dict = result
            for part in key_parts[:-1]:
                if part not in current_dict:
                    current_dict[part] = {}
                elif not isinstance(current_dict[part], dict):
                    # Can't override non-dict values with nested keys
                    break
                current_dict = current_dict[part]
            else:
                # Set the final value with type conversion
                final_key = key_parts[-1]
                current_dict[final_key] = self._convert_env_value(env_value)
        
        return result

    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type.
        
        Args:
            value: Environment variable value as string
            
        Returns:
            Converted value with appropriate type
        """
        # Handle boolean values
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        
        # Handle numeric values
        try:
            if "." in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Return as string if no conversion applies
        return value

    def get_config(self) -> TestHarnessConfig:
        """Get the current configuration.
        
        Returns:
            Current configuration instance
            
        Raises:
            RuntimeError: If no configuration has been loaded
        """
        if self._config is None:
            raise RuntimeError("No configuration loaded. Call load_config() first.")
        return self._config

    def reload_config(self, profile: str = "default") -> TestHarnessConfig:
        """Reload configuration from files.
        
        Args:
            profile: Configuration profile to reload
            
        Returns:
            Reloaded configuration instance
        """
        return self.load_config(profile)

    def validate_config(self, config_data: Dict[str, Any]) -> bool:
        """Validate configuration data without loading it.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            TestHarnessConfig(**config_data)
            return True
        except ValidationError:
            return False


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(config_dir: Optional[Path] = None) -> ConfigLoader:
    """Get the global configuration loader instance.
    
    Args:
        config_dir: Configuration directory (only used on first call)
        
    Returns:
        Global ConfigLoader instance
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_dir)
    return _config_loader


def load_config(profile: str = "default", config_dir: Optional[Path] = None) -> TestHarnessConfig:
    """Load configuration with the specified profile.
    
    Args:
        profile: Configuration profile to load
        config_dir: Configuration directory (optional)
        
    Returns:
        Loaded configuration instance
    """
    loader = get_config_loader(config_dir)
    return loader.load_config(profile)