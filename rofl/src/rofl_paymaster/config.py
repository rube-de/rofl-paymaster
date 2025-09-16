"""Configuration management for ROFL Paymaster."""

import os
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Web3Config(BaseModel):
    """Web3 connection configuration."""

    rpc_urls: List[str] = Field(
        ..., min_length=1, description="RPC endpoint URLs with failover support"
    )
    websocket_urls: Optional[List[str]] = Field(
        None, description="WebSocket URLs for event monitoring"
    )
    chain_id: int = Field(..., description="Chain ID for network validation")
    timeout: int = Field(30, ge=5, le=300, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=1, le=10, description="Maximum retry attempts")
    retry_delay: float = Field(
        1.0, ge=0.1, le=60.0, description="Delay between retries in seconds"
    )

    @field_validator("rpc_urls")
    @classmethod
    def validate_rpc_urls(cls, v):
        """Validate RPC URLs format."""
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid RPC URL format: {url}")
        return v

    @field_validator("websocket_urls")
    @classmethod
    def validate_websocket_urls(cls, v):
        """Validate WebSocket URLs format."""
        if v:
            for url in v:
                if not url.startswith(("ws://", "wss://")):
                    raise ValueError(f"Invalid WebSocket URL format: {url}")
        return v


class ContractConfig(BaseModel):
    """Smart contract configuration."""

    address: str = Field(
        ..., min_length=42, max_length=42, description="Contract address"
    )
    abi_path: Optional[str] = Field(None, description="Path to contract ABI file")
    deployment_block: Optional[int] = Field(
        None, ge=0, description="Block number when contract was deployed"
    )

    @field_validator("address")
    @classmethod
    def validate_address(cls, v):
        """Validate Ethereum address format."""
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError(f"Invalid Ethereum address format: {v}")
        return v.lower()


class MonitoringConfig(BaseModel):
    """Event monitoring configuration."""

    confirmation_blocks: int = Field(
        12, ge=1, le=100, description="Blocks to wait for confirmation"
    )
    event_batch_size: int = Field(
        1000, ge=1, le=10000, description="Batch size for event queries"
    )
    poll_interval: float = Field(
        2.0, ge=0.1, le=60.0, description="Polling interval in seconds"
    )
    max_block_range: int = Field(
        10000, ge=100, le=100000, description="Maximum block range per query"
    )
    reconnect_delay: float = Field(
        5.0, ge=1.0, le=300.0, description="WebSocket reconnection delay"
    )


class OracleConfig(BaseModel):
    """Price oracle configuration."""

    contract: ContractConfig = Field(
        ..., description="Price oracle contract configuration"
    )
    cache_ttl: int = Field(
        300, ge=60, le=3600, description="Price cache TTL in seconds"
    )
    price_bounds: Dict[str, float] = Field(
        default_factory=lambda: {"min": 0.01, "max": 10.0},
        description="Price validation bounds in USD",
    )
    slippage_protection: float = Field(
        0.005, ge=0.0, le=0.1, description="Slippage protection as decimal"
    )
    stale_threshold: int = Field(
        3600, ge=300, le=86400, description="Stale price threshold in seconds"
    )

    @field_validator("price_bounds")
    @classmethod
    def validate_price_bounds(cls, v):
        """Validate price bounds configuration."""
        if "min" not in v or "max" not in v:
            raise ValueError("Price bounds must include 'min' and 'max' values")
        if v["min"] >= v["max"]:
            raise ValueError("Price min must be less than max")
        if v["min"] <= 0:
            raise ValueError("Price min must be positive")
        return v


class ProofConfig(BaseModel):
    """Proof generation configuration."""

    cache_enabled: bool = Field(True, description="Enable proof caching")
    cache_ttl: int = Field(
        3600, ge=300, le=86400, description="Proof cache TTL in seconds"
    )
    generation_timeout: int = Field(
        30, ge=5, le=300, description="Proof generation timeout in seconds"
    )
    validation_enabled: bool = Field(True, description="Enable proof validation")
    parallel_processing: bool = Field(
        True, description="Enable parallel proof processing"
    )


class SecurityConfig(BaseModel):
    """Security configuration."""

    private_key_env: str = Field(
        "PAYMASTER_PRIVATE_KEY", description="Environment variable for private key"
    )
    rate_limit_per_minute: int = Field(
        60, ge=1, le=1000, description="Rate limit per minute"
    )
    max_concurrent_processing: int = Field(
        10, ge=1, le=100, description="Max concurrent deposit processing"
    )
    audit_logging: bool = Field(True, description="Enable audit logging")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field("INFO", description="Log level")
    format: str = Field("json", description="Log format (json or text)")
    file_path: Optional[str] = Field(None, description="Log file path")
    max_file_size: int = Field(
        100 * 1024 * 1024, ge=1024, description="Max log file size in bytes"
    )
    backup_count: int = Field(5, ge=1, le=50, description="Number of backup log files")
    correlation_id: bool = Field(True, description="Include correlation IDs in logs")

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v.upper()

    @field_validator("format")
    @classmethod
    def validate_log_format(cls, v):
        """Validate log format."""
        if v not in ["json", "text"]:
            raise ValueError("Log format must be 'json' or 'text'")
        return v


class Config(BaseSettings):
    """Main application configuration."""

    # Network configurations
    base_chain: Web3Config = Field(..., description="Base L2 chain configuration")
    sapphire_chain: Web3Config = Field(
        ..., description="Oasis Sapphire chain configuration"
    )

    # Contract configurations
    vault_contract: ContractConfig = Field(
        ..., description="Base vault contract configuration"
    )
    paymaster_contract: ContractConfig = Field(
        ..., description="Sapphire paymaster contract configuration"
    )
    blockhash_oracle: ContractConfig = Field(
        ..., description="Blockhash oracle contract configuration"
    )

    # Service configurations
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    price_oracle: OracleConfig = Field(..., description="Price oracle configuration")
    proof_generation: ProofConfig = Field(default_factory=ProofConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Application settings
    app_name: str = Field("rofl-paymaster", description="Application name")
    version: str = Field("0.1.0", description="Application version")
    debug: bool = Field(False, description="Debug mode")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
        "case_sensitive": False
    }

    @model_validator(mode="after")
    def validate_chain_ids(self):
        """Validate that Base and Sapphire have different chain IDs."""
        if self.base_chain and self.sapphire_chain:
            if self.base_chain.chain_id == self.sapphire_chain.chain_id:
                raise ValueError(
                    "Base and Sapphire chains must have different chain IDs"
                )

        return self


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from YAML file with environment variable substitution.

    Args:
        config_path: Path to configuration file. Defaults to 'config.yaml'

    Returns:
        Loaded and validated configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
        yaml.YAMLError: If YAML parsing fails
    """
    if config_path is None:
        config_path = os.getenv("PAYMASTER_CONFIG_PATH", "config.yaml")

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse YAML configuration: {e}")

    # Substitute environment variables
    config_data = _substitute_env_vars(raw_config)

    try:
        return Config(**config_data)
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")


def _substitute_env_vars(data: Any) -> Any:
    """Recursively substitute environment variables in configuration data.

    Supports ${VAR_NAME} and ${VAR_NAME:default_value} syntax.

    Args:
        data: Configuration data to process

    Returns:
        Data with environment variables substituted
    """
    if isinstance(data, dict):
        return {key: _substitute_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_substitute_env_vars(item) for item in data]
    elif isinstance(data, str):
        return _substitute_string_env_vars(data)
    else:
        return data


def _substitute_string_env_vars(text: str) -> str:
    """Substitute environment variables in a string.

    Args:
        text: String potentially containing ${VAR} or ${VAR:default} patterns

    Returns:
        String with environment variables substituted
    """
    import re

    def replace_var(match):
        var_expr = match.group(1)
        if ":" in var_expr:
            var_name, default_value = var_expr.split(":", 1)
            return os.getenv(var_name, default_value)
        else:
            var_value = os.getenv(var_expr)
            if var_value is None:
                raise ValueError(
                    f"Environment variable {var_expr} is required but not set"
                )
            return var_value

    # Match ${VAR_NAME} or ${VAR_NAME:default}
    pattern = r"\$\{([^}]+)\}"
    return re.sub(pattern, replace_var, text)


def create_sample_config(output_path: str = "config.yaml.sample") -> None:
    """Create a sample configuration file with documentation.

    Args:
        output_path: Path where to write the sample configuration
    """
    sample_config = {
        "app_name": "rofl-paymaster",
        "version": "0.1.0",
        "debug": False,
        "base_chain": {
            "rpc_urls": [
                "https://mainnet.base.org",
                "https://base-mainnet.public.blastapi.io",
            ],
            "websocket_urls": [
                "wss://mainnet.base.org",
                "wss://base-mainnet.public.blastapi.io",
            ],
            "chain_id": 8453,
            "timeout": 30,
            "max_retries": 3,
            "retry_delay": 1.0,
        },
        "sapphire_chain": {
            "rpc_urls": ["https://sapphire.oasis.io", "https://1rpc.io/oasis/sapphire"],
            "websocket_urls": ["wss://sapphire.oasis.io/ws"],
            "chain_id": 23294,
            "timeout": 30,
            "max_retries": 3,
            "retry_delay": 1.0,
        },
        "vault_contract": {
            "address": "${BASE_VAULT_CONTRACT_ADDRESS}",
            "deployment_block": "${BASE_VAULT_DEPLOYMENT_BLOCK:0}",
        },
        "paymaster_contract": {
            "address": "${SAPPHIRE_PAYMASTER_CONTRACT_ADDRESS}",
            "deployment_block": "${SAPPHIRE_PAYMASTER_DEPLOYMENT_BLOCK:0}",
        },
        "blockhash_oracle": {
            "address": "${BLOCKHASH_ORACLE_CONTRACT_ADDRESS}",
            "deployment_block": "${BLOCKHASH_ORACLE_DEPLOYMENT_BLOCK:0}",
        },
        "monitoring": {
            "confirmation_blocks": 12,
            "event_batch_size": 1000,
            "poll_interval": 2.0,
            "max_block_range": 10000,
            "reconnect_delay": 5.0,
        },
        "price_oracle": {
            "contract": {"address": "${PRICE_ORACLE_CONTRACT_ADDRESS}"},
            "cache_ttl": 300,
            "price_bounds": {"min": 0.01, "max": 10.0},
            "slippage_protection": 0.005,
            "stale_threshold": 3600,
        },
        "proof_generation": {
            "cache_enabled": True,
            "cache_ttl": 3600,
            "generation_timeout": 30,
            "validation_enabled": True,
            "parallel_processing": True,
        },
        "security": {
            "private_key_env": "PAYMASTER_PRIVATE_KEY",
            "rate_limit_per_minute": 60,
            "max_concurrent_processing": 10,
            "audit_logging": True,
        },
        "logging": {
            "level": "INFO",
            "format": "json",
            "file_path": None,
            "max_file_size": 104857600,
            "backup_count": 5,
            "correlation_id": True,
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config, f, default_flow_style=False, indent=2, sort_keys=False)

    print(f"Sample configuration created at: {output_path}")
    print("\nTo use this configuration:")
    print(f"1. Copy {output_path} to config.yaml")
    print("2. Set required environment variables")
    print("3. Customize settings as needed")
