"""Tests for environment variable management."""

import os
import tempfile
import pytest
from pathlib import Path

from rofl_paymaster.env import (
    EnvironmentManager,
    _validate_eth_address,
    _validate_private_key,
    _validate_block_number,
    _validate_port,
    _validate_log_level,
    _validate_boolean,
)


def test_validate_eth_address():
    """Test Ethereum address validation."""
    # Valid addresses
    valid_addresses = [
        "0x1234567890123456789012345678901234567890",
        "0xAbCdEf1234567890123456789012345678901234",
        "0x0000000000000000000000000000000000000000",
    ]

    for address in valid_addresses:
        _validate_eth_address(address)  # Should not raise

    # Invalid addresses
    invalid_addresses = [
        "1234567890123456789012345678901234567890",  # Missing 0x
        "0x123456789012345678901234567890123456789",  # Too short
        "0x12345678901234567890123456789012345678901",  # Too long
        "0xGHIJ567890123456789012345678901234567890",  # Invalid hex
        "",  # Empty
    ]

    for address in invalid_addresses:
        with pytest.raises(ValueError):
            _validate_eth_address(address)


def test_validate_private_key():
    """Test private key validation."""
    # Note: We can't easily test a "valid" private key without generating one
    # So we test the format validation instead

    # Invalid formats
    invalid_keys = [
        "1234567890123456789012345678901234567890123456789012345678901234",  # Missing 0x
        "0x123456789012345678901234567890123456789012345678901234567890123",  # Too short
        "0x12345678901234567890123456789012345678901234567890123456789012345",  # Too long
        "0xGHIJ567890123456789012345678901234567890123456789012345678901234",  # Invalid hex
    ]

    for key in invalid_keys:
        with pytest.raises(ValueError):
            _validate_private_key(key)


def test_validate_block_number():
    """Test block number validation."""
    # Valid block numbers
    valid_blocks = ["0", "123", "999999"]

    for block in valid_blocks:
        _validate_block_number(block)  # Should not raise

    # Invalid block numbers
    invalid_blocks = ["abc", "-1", "12.5", ""]

    for block in invalid_blocks:
        with pytest.raises(ValueError):
            _validate_block_number(block)


def test_validate_port():
    """Test port validation."""
    # Valid ports
    valid_ports = ["1", "80", "8000", "65535"]

    for port in valid_ports:
        _validate_port(port)  # Should not raise

    # Invalid ports
    invalid_ports = ["0", "65536", "abc", "-1", ""]

    for port in invalid_ports:
        with pytest.raises(ValueError):
            _validate_port(port)


def test_validate_log_level():
    """Test log level validation."""
    # Valid levels
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "debug", "info"]

    for level in valid_levels:
        _validate_log_level(level)  # Should not raise

    # Invalid levels
    invalid_levels = ["TRACE", "VERBOSE", "abc", ""]

    for level in invalid_levels:
        with pytest.raises(ValueError):
            _validate_log_level(level)


def test_validate_boolean():
    """Test boolean validation."""
    # Valid boolean values
    valid_bools = ["true", "false", "True", "False", "1", "0", "yes", "no", "YES", "NO"]

    for bool_val in valid_bools:
        _validate_boolean(bool_val)  # Should not raise

    # Invalid boolean values
    invalid_bools = ["maybe", "2", "abc", ""]

    for bool_val in invalid_bools:
        with pytest.raises(ValueError):
            _validate_boolean(bool_val)


def test_environment_manager_validation():
    """Test environment manager validation."""
    env_manager = EnvironmentManager()

    # Test with missing required variables
    original_env = dict(os.environ)

    try:
        # Clear environment
        for var in env_manager.ENV_VARS:
            if var.name in os.environ:
                del os.environ[var.name]

        # Should raise ValueError for missing required variables
        with pytest.raises(ValueError, match="Environment validation failed"):
            env_manager.validate_environment()

    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_environment_manager_get_env():
    """Test getting environment variables."""
    env_manager = EnvironmentManager()

    # Test with default value
    value = env_manager.get_env("NONEXISTENT_VAR", "default_value")
    assert value == "default_value"

    # Test without default for missing variable
    with pytest.raises(ValueError):
        env_manager.get_env("NONEXISTENT_VAR")


def test_create_env_file():
    """Test creating environment file."""
    env_manager = EnvironmentManager()

    with tempfile.TemporaryDirectory() as temp_dir:
        env_path = Path(temp_dir) / ".env.test"
        env_manager.create_env_file(str(env_path))

        assert env_path.exists()

        content = env_path.read_text()
        assert "ROFL Paymaster Environment Configuration" in content
        assert "BASE_VAULT_CONTRACT_ADDRESS" in content
        assert "PAYMASTER_PRIVATE_KEY" in content


def test_generate_encryption_key():
    """Test encryption key generation."""
    env_manager = EnvironmentManager()

    key = env_manager.generate_encryption_key()
    assert isinstance(key, str)
    assert len(key) > 0

    # Should be valid base64
    import base64

    decoded = base64.b64decode(key)
    assert len(decoded) >= 32
