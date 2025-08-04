"""Tests for configuration management."""

import os
import tempfile
import pytest
from pathlib import Path
from pydantic import ValidationError

from rofl_paymaster.config import Config, load_config, create_sample_config


def test_config_validation():
    """Test configuration validation."""
    # Valid minimal configuration
    valid_config = {
        "base_chain": {"rpc_urls": ["https://mainnet.base.org"], "chain_id": 8453},
        "sapphire_chain": {
            "rpc_urls": ["https://sapphire.oasis.io"],
            "chain_id": 23294,
        },
        "vault_contract": {"address": "0x1234567890123456789012345678901234567890"},
        "paymaster_contract": {"address": "0x1234567890123456789012345678901234567891"},
        "blockhash_oracle": {"address": "0x1234567890123456789012345678901234567892"},
        "price_oracle": {
            "contract": {"address": "0x1234567890123456789012345678901234567893"}
        },
    }

    config = Config(**valid_config)
    assert config.base_chain.chain_id == 8453
    assert config.sapphire_chain.chain_id == 23294


def test_config_validation_errors():
    """Test configuration validation errors."""
    # Invalid chain IDs (same for both chains)
    invalid_config = {
        "base_chain": {"rpc_urls": ["https://mainnet.base.org"], "chain_id": 8453},
        "sapphire_chain": {
            "rpc_urls": ["https://sapphire.oasis.io"],
            "chain_id": 8453,  # Same as base_chain
        },
        "vault_contract": {"address": "0x1234567890123456789012345678901234567890"},
        "paymaster_contract": {"address": "0x1234567890123456789012345678901234567891"},
        "blockhash_oracle": {"address": "0x1234567890123456789012345678901234567892"},
        "price_oracle": {
            "contract": {"address": "0x1234567890123456789012345678901234567893"}
        },
    }

    with pytest.raises(ValidationError):
        Config(**invalid_config)


def test_invalid_ethereum_address():
    """Test invalid Ethereum address validation."""
    invalid_config = {
        "base_chain": {"rpc_urls": ["https://mainnet.base.org"], "chain_id": 8453},
        "sapphire_chain": {
            "rpc_urls": ["https://sapphire.oasis.io"],
            "chain_id": 23294,
        },
        "vault_contract": {"address": "invalid_address"},  # Invalid address
        "paymaster_contract": {"address": "0x1234567890123456789012345678901234567891"},
        "blockhash_oracle": {"address": "0x1234567890123456789012345678901234567892"},
        "price_oracle": {
            "contract": {"address": "0x1234567890123456789012345678901234567893"}
        },
    }

    with pytest.raises(ValidationError):
        Config(**invalid_config)


def test_load_config_file_not_found():
    """Test loading configuration when file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent_config.yaml")


def test_create_sample_config():
    """Test creating sample configuration file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_config.yaml"
        create_sample_config(str(config_path))

        assert config_path.exists()

        # Verify the file contains expected content
        content = config_path.read_text()
        assert "app_name" in content
        assert "base_chain" in content
        assert "sapphire_chain" in content


def test_price_bounds_validation():
    """Test price bounds validation."""
    # Valid price bounds
    valid_bounds = {"min": 0.01, "max": 10.0}

    config_data = {
        "base_chain": {"rpc_urls": ["https://mainnet.base.org"], "chain_id": 8453},
        "sapphire_chain": {
            "rpc_urls": ["https://sapphire.oasis.io"],
            "chain_id": 23294,
        },
        "vault_contract": {"address": "0x1234567890123456789012345678901234567890"},
        "paymaster_contract": {"address": "0x1234567890123456789012345678901234567891"},
        "blockhash_oracle": {"address": "0x1234567890123456789012345678901234567892"},
        "price_oracle": {
            "contract": {"address": "0x1234567890123456789012345678901234567893"},
            "price_bounds": valid_bounds,
        },
    }

    config = Config(**config_data)
    assert config.price_oracle.price_bounds["min"] == 0.01
    assert config.price_oracle.price_bounds["max"] == 10.0

    # Invalid price bounds (min >= max)
    invalid_bounds = {"min": 10.0, "max": 1.0}

    config_data["price_oracle"]["price_bounds"] = invalid_bounds

    with pytest.raises(ValidationError):
        Config(**config_data)
