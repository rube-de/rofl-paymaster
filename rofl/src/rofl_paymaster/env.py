"""Environment variable management for ROFL Paymaster."""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from eth_account import Account
from cryptography.fernet import Fernet
import base64


@dataclass
class EnvVar:
    """Environment variable definition."""

    name: str
    description: str
    required: bool = True
    default: Optional[str] = None
    sensitive: bool = False
    validation_func: Optional[callable] = None


class EnvironmentManager:
    """Manages environment variables and secrets for the application."""

    # Define all environment variables used by the application
    ENV_VARS = [
        # Network Configuration
        EnvVar(
            name="PAYMASTER_CONFIG_PATH",
            description="Path to the configuration YAML file",
            required=False,
            default="config.yaml",
        ),
        # Contract Addresses
        EnvVar(
            name="BASE_VAULT_CONTRACT_ADDRESS",
            description="Base L2 vault contract address",
            required=True,
            validation_func=lambda x: _validate_eth_address(x),
        ),
        EnvVar(
            name="SAPPHIRE_PAYMASTER_CONTRACT_ADDRESS",
            description="Oasis Sapphire paymaster contract address",
            required=True,
            validation_func=lambda x: _validate_eth_address(x),
        ),
        EnvVar(
            name="BLOCKHASH_ORACLE_CONTRACT_ADDRESS",
            description="Blockhash oracle contract address on Sapphire",
            required=True,
            validation_func=lambda x: _validate_eth_address(x),
        ),
        EnvVar(
            name="PRICE_ORACLE_CONTRACT_ADDRESS",
            description="Price oracle contract address on Sapphire",
            required=True,
            validation_func=lambda x: _validate_eth_address(x),
        ),
        # Deployment Block Numbers
        EnvVar(
            name="BASE_VAULT_DEPLOYMENT_BLOCK",
            description="Block number when Base vault contract was deployed",
            required=False,
            default="0",
            validation_func=lambda x: _validate_block_number(x),
        ),
        EnvVar(
            name="SAPPHIRE_PAYMASTER_DEPLOYMENT_BLOCK",
            description="Block number when Sapphire paymaster was deployed",
            required=False,
            default="0",
            validation_func=lambda x: _validate_block_number(x),
        ),
        EnvVar(
            name="BLOCKHASH_ORACLE_DEPLOYMENT_BLOCK",
            description="Block number when blockhash oracle was deployed",
            required=False,
            default="0",
            validation_func=lambda x: _validate_block_number(x),
        ),
        # Secrets
        EnvVar(
            name="PAYMASTER_PRIVATE_KEY",
            description="Private key for the paymaster account (0x prefixed hex)",
            required=True,
            sensitive=True,
            validation_func=lambda x: _validate_private_key(x),
        ),
        # Optional Encryption
        EnvVar(
            name="PAYMASTER_ENCRYPTION_KEY",
            description="Base64 encoded encryption key for sensitive data",
            required=False,
            sensitive=True,
            validation_func=lambda x: _validate_encryption_key(x),
        ),
        # Database/Storage
        EnvVar(
            name="PAYMASTER_DATA_DIR",
            description="Directory for storing application data",
            required=False,
            default="./data",
        ),
        # API Configuration
        EnvVar(
            name="PAYMASTER_API_HOST",
            description="Host address for the API server",
            required=False,
            default="0.0.0.0",
        ),
        EnvVar(
            name="PAYMASTER_API_PORT",
            description="Port for the API server",
            required=False,
            default="8000",
            validation_func=lambda x: _validate_port(x),
        ),
        # RPC Configuration
        EnvVar(
            name="BASE_RPC_URLS",
            description="Comma-separated Base L2 RPC URLs",
            required=False,
        ),
        EnvVar(
            name="SAPPHIRE_RPC_URLS",
            description="Comma-separated Oasis Sapphire RPC URLs",
            required=False,
        ),
        EnvVar(
            name="BASE_WS_URLS",
            description="Comma-separated Base L2 WebSocket URLs",
            required=False,
        ),
        EnvVar(
            name="SAPPHIRE_WS_URLS",
            description="Comma-separated Oasis Sapphire WebSocket URLs",
            required=False,
        ),
        # Logging
        EnvVar(
            name="PAYMASTER_LOG_LEVEL",
            description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
            required=False,
            default="INFO",
            validation_func=lambda x: _validate_log_level(x),
        ),
        EnvVar(
            name="PAYMASTER_LOG_FILE",
            description="Path to log file (optional)",
            required=False,
        ),
        # Development/Testing
        EnvVar(
            name="PAYMASTER_DEBUG",
            description="Enable debug mode (true/false)",
            required=False,
            default="false",
            validation_func=lambda x: _validate_boolean(x),
        ),
        EnvVar(
            name="PAYMASTER_TEST_MODE",
            description="Enable test mode with mock contracts (true/false)",
            required=False,
            default="false",
            validation_func=lambda x: _validate_boolean(x),
        ),
    ]

    def __init__(self):
        """Initialize environment manager."""
        self._validated_vars: Dict[str, str] = {}
        self._encryption_key: Optional[bytes] = None

    def validate_environment(self) -> Dict[str, Any]:
        """Validate all environment variables.

        Returns:
            Dictionary of validation results

        Raises:
            ValueError: If required variables are missing or invalid
        """
        results = {
            "valid": True,
            "missing_required": [],
            "invalid_values": [],
            "warnings": [],
        }

        for env_var in self.ENV_VARS:
            value = os.getenv(env_var.name)

            if value is None:
                if env_var.required:
                    results["missing_required"].append(env_var.name)
                    results["valid"] = False
                elif env_var.default is not None:
                    self._validated_vars[env_var.name] = env_var.default
            else:
                # Validate the value if a validation function is provided
                if env_var.validation_func:
                    try:
                        env_var.validation_func(value)
                        self._validated_vars[env_var.name] = value
                    except ValueError as e:
                        results["invalid_values"].append(
                            {
                                "name": env_var.name,
                                "value": "***" if env_var.sensitive else value,
                                "error": str(e),
                            }
                        )
                        results["valid"] = False
                else:
                    self._validated_vars[env_var.name] = value

        if not results["valid"]:
            error_msg = "Environment validation failed:\n"
            if results["missing_required"]:
                missing = ", ".join(results["missing_required"])
                error_msg += f"Missing required variables: {missing}\n"
            if results["invalid_values"]:
                for invalid in results["invalid_values"]:
                    error_msg += f"Invalid {invalid['name']}: {invalid['error']}\n"
            raise ValueError(error_msg.strip())

        return results

    def get_env(self, name: str, default: Optional[str] = None) -> str:
        """Get environment variable value with validation.

        Args:
            name: Environment variable name
            default: Default value if not set

        Returns:
            Environment variable value

        Raises:
            ValueError: If variable is not set and no default provided
        """
        if name in self._validated_vars:
            return self._validated_vars[name]

        value = os.getenv(name, default)
        if value is None:
            raise ValueError(f"Environment variable {name} is not set")

        return value

    def get_private_key(self) -> str:
        """Get the paymaster private key securely.

        Returns:
            Private key as hex string

        Raises:
            ValueError: If private key is not configured or invalid
        """
        private_key = self.get_env("PAYMASTER_PRIVATE_KEY")

        # Validate the private key format and create account to verify
        try:
            Account.from_key(private_key)
            return private_key
        except Exception as e:
            raise ValueError(f"Invalid private key format: {e}")

    def get_account(self) -> Account:
        """Get the paymaster account object.

        Returns:
            eth_account.Account object
        """
        private_key = self.get_private_key()
        return Account.from_key(private_key)

    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data using the encryption key.

        Args:
            data: Data to encrypt

        Returns:
            Base64 encoded encrypted data

        Raises:
            ValueError: If encryption key is not configured
        """
        if self._encryption_key is None:
            key_str = self.get_env("PAYMASTER_ENCRYPTION_KEY")
            if not key_str:
                raise ValueError("Encryption key not configured")
            self._encryption_key = base64.b64decode(key_str)

        fernet = Fernet(base64.b64encode(self._encryption_key[:32]))
        encrypted_data = fernet.encrypt(data.encode("utf-8"))
        return base64.b64encode(encrypted_data).decode("utf-8")

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data using the encryption key.

        Args:
            encrypted_data: Base64 encoded encrypted data

        Returns:
            Decrypted data

        Raises:
            ValueError: If encryption key is not configured or decryption fails
        """
        if self._encryption_key is None:
            key_str = self.get_env("PAYMASTER_ENCRYPTION_KEY")
            if not key_str:
                raise ValueError("Encryption key not configured")
            self._encryption_key = base64.b64decode(key_str)

        try:
            fernet = Fernet(base64.b64encode(self._encryption_key[:32]))
            encrypted_bytes = base64.b64decode(encrypted_data)
            decrypted_data = fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {e}")

    def generate_encryption_key(self) -> str:
        """Generate a new encryption key.

        Returns:
            Base64 encoded encryption key
        """
        key = Fernet.generate_key()
        return base64.b64encode(key).decode("utf-8")

    def create_env_file(self, output_path: str = ".env.example") -> None:
        """Create an example environment file.

        Args:
            output_path: Path to write the environment file
        """
        lines = [
            "# ROFL Paymaster Environment Configuration",
            "# Copy this file to .env and fill in the values",
            "",
        ]

        # Group variables by category
        categories = {
            "Configuration": ["PAYMASTER_CONFIG_PATH"],
            "Contract Addresses": [
                "BASE_VAULT_CONTRACT_ADDRESS",
                "SAPPHIRE_PAYMASTER_CONTRACT_ADDRESS",
                "BLOCKHASH_ORACLE_CONTRACT_ADDRESS",
                "PRICE_ORACLE_CONTRACT_ADDRESS",
            ],
            "Deployment Blocks": [
                "BASE_VAULT_DEPLOYMENT_BLOCK",
                "SAPPHIRE_PAYMASTER_DEPLOYMENT_BLOCK",
                "BLOCKHASH_ORACLE_DEPLOYMENT_BLOCK",
            ],
            "Secrets": ["PAYMASTER_PRIVATE_KEY", "PAYMASTER_ENCRYPTION_KEY"],
            "RPC Configuration": [
                "BASE_RPC_URLS",
                "SAPPHIRE_RPC_URLS",
                "BASE_WS_URLS",
                "SAPPHIRE_WS_URLS",
            ],
            "Application Settings": [
                "PAYMASTER_DATA_DIR",
                "PAYMASTER_API_HOST",
                "PAYMASTER_API_PORT",
            ],
            "Logging": ["PAYMASTER_LOG_LEVEL", "PAYMASTER_LOG_FILE"],
            "Development": ["PAYMASTER_DEBUG", "PAYMASTER_TEST_MODE"],
        }

        env_var_dict = {var.name: var for var in self.ENV_VARS}

        for category, var_names in categories.items():
            lines.append(f"# {category}")
            for var_name in var_names:
                if var_name in env_var_dict:
                    var = env_var_dict[var_name]
                    lines.append(f"# {var.description}")
                    if var.sensitive:
                        lines.append(f"# {var_name}=")
                    else:
                        default_val = var.default or ""
                        lines.append(f"{var_name}={default_val}")
            lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"Example environment file created at: {output_path}")


def _validate_eth_address(address: str) -> None:
    """Validate Ethereum address format."""
    if not address.startswith("0x") or len(address) != 42:
        raise ValueError("Must be a valid Ethereum address (0x + 40 hex characters)")

    try:
        int(address[2:], 16)
    except ValueError:
        raise ValueError("Address must contain only hexadecimal characters")


def _validate_private_key(private_key: str) -> None:
    """Validate private key format."""
    if not private_key.startswith("0x"):
        raise ValueError("Private key must start with 0x")

    if len(private_key) != 66:
        raise ValueError("Private key must be 64 hex characters (66 with 0x prefix)")

    try:
        int(private_key[2:], 16)
    except ValueError:
        raise ValueError("Private key must contain only hexadecimal characters")

    # Verify it can create a valid account
    try:
        Account.from_key(private_key)
    except Exception:
        raise ValueError("Invalid private key format")


def _validate_block_number(block_str: str) -> None:
    """Validate block number format."""
    try:
        block_num = int(block_str)
        if block_num < 0:
            raise ValueError("Block number must be non-negative")
    except ValueError:
        raise ValueError("Block number must be a valid integer")


def _validate_port(port_str: str) -> None:
    """Validate port number."""
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError("Port must be between 1 and 65535")
    except ValueError:
        raise ValueError("Port must be a valid integer")


def _validate_log_level(level: str) -> None:
    """Validate log level."""
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if level.upper() not in valid_levels:
        raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")


def _validate_boolean(value: str) -> None:
    """Validate boolean string."""
    if value.lower() not in ["true", "false", "1", "0", "yes", "no"]:
        raise ValueError("Boolean value must be true, false, 1, 0, yes, or no")


def _validate_encryption_key(key_str: str) -> None:
    """Validate encryption key format."""
    try:
        key_bytes = base64.b64decode(key_str)
        if len(key_bytes) < 32:
            raise ValueError("Encryption key must be at least 32 bytes when decoded")
    except Exception:
        raise ValueError("Encryption key must be valid base64")


# Global environment manager instance
env_manager = EnvironmentManager()
