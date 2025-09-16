"""Tests for custom exception classes."""

import pytest

from rofl_paymaster.exceptions import (
    PaymasterError, ConfigurationError, ConnectionError, Web3Error,
    DepositError, ProofGenerationError, ValidationError, PriceOracleError,
    TransactionError, EventMonitoringError, BlockhashOracleError,
    SecurityError, RateLimitError, CircuitBreakerError, RetryableError,
    TemporaryError, PermanentError, is_retryable_error, get_retry_delay,
    categorize_error
)


class TestPaymasterError:
    """Test base PaymasterError class."""
    
    def test_paymaster_error_basic(self):
        """Test basic PaymasterError creation."""
        error = PaymasterError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.error_code is None
        assert error.details == {}
    
    def test_paymaster_error_with_details(self):
        """Test PaymasterError with error code and details."""
        details = {"key": "value", "number": 42}
        error = PaymasterError("Test error", "TEST_ERROR", details)
        
        assert error.error_code == "TEST_ERROR"
        assert error.details == details
    
    def test_paymaster_error_to_dict(self):
        """Test PaymasterError serialization to dict."""
        details = {"context": "test"}
        error = PaymasterError("Test error", "TEST_ERROR", details)
        
        error_dict = error.to_dict()
        
        assert error_dict["error_type"] == "PaymasterError"
        assert error_dict["message"] == "Test error"
        assert error_dict["error_code"] == "TEST_ERROR"
        assert error_dict["details"] == details


class TestSpecificErrors:
    """Test specific error classes."""
    
    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Invalid config", "database_url")
        
        assert error.error_code == "CONFIG_ERROR_DATABASE_URL"
        assert error.details["config_key"] == "database_url"
    
    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Connection failed", "https://rpc.example.com", 8453)
        
        assert error.error_code == "CONNECTION_ERROR"
        assert error.details["provider_url"] == "https://rpc.example.com"
        assert error.details["chain_id"] == 8453
    
    def test_web3_error(self):
        """Test Web3Error."""
        tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        error = Web3Error("Transaction failed", "send_transaction", tx_hash)
        
        assert error.error_code == "WEB3_ERROR_SEND_TRANSACTION"
        assert error.details["method"] == "send_transaction"
        assert error.details["transaction_hash"] == tx_hash
    
    def test_deposit_error(self):
        """Test DepositError."""
        deposit_id = "0x1234:0"
        error = DepositError("Deposit processing failed", deposit_id, "proof_generation")
        
        assert error.error_code == "DEPOSIT_ERROR_PROOF_GENERATION"
        assert error.details["deposit_id"] == deposit_id
        assert error.details["stage"] == "proof_generation"
    
    def test_proof_generation_error(self):
        """Test ProofGenerationError."""
        tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        error = ProofGenerationError("Proof failed", 12345, tx_hash, "merkle_tree")
        
        assert error.error_code == "PROOF_ERROR_MERKLE_TREE"
        assert error.details["block_number"] == 12345
        assert error.details["transaction_hash"] == tx_hash
        assert error.details["proof_type"] == "merkle_tree"
    
    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Invalid value", "amount", "negative")
        
        assert error.error_code == "VALIDATION_ERROR_AMOUNT"
        assert error.details["field"] == "amount"
        assert error.details["value"] == "negative"
    
    def test_price_oracle_error(self):
        """Test PriceOracleError."""
        oracle_addr = "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800"
        error = PriceOracleError("Oracle unavailable", oracle_addr, "get_price")
        
        assert error.error_code == "ORACLE_ERROR_GET_PRICE"
        assert error.details["oracle_address"] == oracle_addr
        assert error.details["operation"] == "get_price"
    
    def test_transaction_error(self):
        """Test TransactionError."""
        tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        error = TransactionError("Tx failed", tx_hash, 42, "gas_estimation")
        
        assert error.error_code == "TX_ERROR_GAS_ESTIMATION"
        assert error.details["transaction_hash"] == tx_hash
        assert error.details["nonce"] == 42
        assert error.details["operation"] == "gas_estimation"
    
    def test_event_monitoring_error(self):
        """Test EventMonitoringError."""
        contract_addr = "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800"
        event_sig = "0x1234567890abcdef"
        block_range = (12345, 12400)
        
        error = EventMonitoringError("Event monitoring failed", contract_addr, event_sig, block_range)
        
        assert error.error_code == "EVENT_MONITORING_ERROR"
        assert error.details["contract_address"] == contract_addr
        assert error.details["event_signature"] == event_sig
        assert error.details["block_range"] == block_range
    
    def test_blockhash_oracle_error(self):
        """Test BlockhashOracleError."""
        oracle_addr = "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800"
        error = BlockhashOracleError("Oracle update failed", oracle_addr, 12345, "update_batch")
        
        assert error.error_code == "BLOCKHASH_ERROR_UPDATE_BATCH"
        assert error.details["oracle_address"] == oracle_addr
        assert error.details["block_number"] == 12345
        assert error.details["operation"] == "update_batch"
    
    def test_security_error(self):
        """Test SecurityError."""
        error = SecurityError("Unauthorized access", "auth_bypass", "critical")
        
        assert error.error_code == "SECURITY_ERROR_AUTH_BYPASS"
        assert error.details["violation_type"] == "auth_bypass"
        assert error.details["severity"] == "critical"
    
    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError("Rate limit exceeded", "rpc_calls", 60.0)
        
        assert error.error_code == "RATE_LIMIT_RPC_CALLS"
        assert error.details["limit_type"] == "rpc_calls"
        assert error.details["retry_after"] == 60.0
    
    def test_circuit_breaker_error(self):
        """Test CircuitBreakerError."""
        error = CircuitBreakerError("Circuit breaker open", "price_oracle", 0.8)
        
        assert error.error_code == "CIRCUIT_BREAKER_PRICE_ORACLE"
        assert error.details["service"] == "price_oracle"
        assert error.details["failure_rate"] == 0.8


class TestRetryableErrors:
    """Test retryable error classes."""
    
    def test_retryable_error(self):
        """Test RetryableError."""
        error = RetryableError("Temporary failure", 30.0, 5, "TEMP_ERROR")
        
        assert error.error_code == "TEMP_ERROR"
        assert error.details["retry_after"] == 30.0
        assert error.details["max_retries"] == 5
        assert error.details["retryable"] is True
    
    def test_temporary_error(self):
        """Test TemporaryError."""
        error = TemporaryError("Service unavailable", "database", 60.0)
        
        assert error.error_code == "TEMPORARY_ERROR_DATABASE"
        assert error.details["service"] == "database"
        assert error.details["retry_after"] == 60.0
        assert error.details["retryable"] is True
    
    def test_permanent_error(self):
        """Test PermanentError."""
        error = PermanentError("Invalid signature", "crypto_validation", "PERM_ERROR")
        
        assert error.error_code == "PERM_ERROR"
        assert error.details["reason"] == "crypto_validation"
        assert error.details["retryable"] is False


class TestErrorUtilities:
    """Test error utility functions."""
    
    def test_is_retryable_error(self):
        """Test is_retryable_error function."""
        # Retryable errors
        assert is_retryable_error(RetryableError("Test"))
        assert is_retryable_error(TemporaryError("Test"))
        assert is_retryable_error(RateLimitError("Test"))
        assert is_retryable_error(ConnectionError("Test"))
        
        # Non-retryable errors
        assert not is_retryable_error(PermanentError("Test"))
        assert not is_retryable_error(ValidationError("Test"))
        assert not is_retryable_error(SecurityError("Test"))
        assert not is_retryable_error(ConfigurationError("Test"))
        
        # Generic exceptions default to False
        assert not is_retryable_error(ValueError("Test"))
    
    def test_get_retry_delay(self):
        """Test get_retry_delay function."""
        # Error with specific retry_after
        error = RetryableError("Test", retry_after=45.0)
        delay = get_retry_delay(error)
        assert delay == 45.0
        
        # Error without retry_after - uses exponential backoff
        error = TemporaryError("Test")
        delay1 = get_retry_delay(error, attempt=1)
        delay2 = get_retry_delay(error, attempt=2)
        delay3 = get_retry_delay(error, attempt=3)
        
        # Should increase with attempt number (exponential backoff)
        assert delay1 < delay2 < delay3
        
        # Should include jitter (randomness)
        delays = [get_retry_delay(error, attempt=2) for _ in range(10)]
        assert len(set(delays)) > 1  # Should have different values due to jitter
    
    def test_get_retry_delay_with_max(self):
        """Test get_retry_delay with max_delay limit."""
        error = TemporaryError("Test")
        
        # High attempt number should be capped by max_delay + jitter (up to 30% of max_delay)
        delay = get_retry_delay(error, attempt=10, max_delay=30.0)
        assert delay <= 39.0  # max_delay + max jitter (30.0 + 0.3 * 30.0)
    
    def test_categorize_error(self):
        """Test categorize_error function."""
        assert categorize_error(SecurityError("Test")) == "security"
        assert categorize_error(ConnectionError("Test")) == "connectivity"
        assert categorize_error(ConfigurationError("Test")) == "configuration"
        assert categorize_error(ValidationError("Test")) == "validation"
        assert categorize_error(ProofGenerationError("Test")) == "proof_generation"
        assert categorize_error(TransactionError("Test")) == "transaction"
        assert categorize_error(EventMonitoringError("Test")) == "event_monitoring"
        assert categorize_error(PriceOracleError("Test")) == "price_oracle"
        assert categorize_error(BlockhashOracleError("Test")) == "blockhash_oracle"
        assert categorize_error(RateLimitError("Test")) == "rate_limiting"
        assert categorize_error(CircuitBreakerError("Test")) == "circuit_breaker"
        assert categorize_error(TemporaryError("Test")) == "temporary"
        assert categorize_error(PermanentError("Test")) == "permanent"
        assert categorize_error(ValueError("Test")) == "unknown"


class TestErrorInheritance:
    """Test error inheritance and relationships."""
    
    def test_inheritance_chain(self):
        """Test that all errors inherit from PaymasterError."""
        errors = [
            ConfigurationError("Test"),
            ConnectionError("Test"),
            Web3Error("Test"),
            DepositError("Test"),
            ProofGenerationError("Test"),
            ValidationError("Test"),
            PriceOracleError("Test"),
            TransactionError("Test"),
            EventMonitoringError("Test"),
            BlockhashOracleError("Test"),
            SecurityError("Test"),
            RateLimitError("Test"),
            CircuitBreakerError("Test"),
            RetryableError("Test", error_code="TEST"),
            TemporaryError("Test"),
            PermanentError("Test"),
        ]
        
        for error in errors:
            assert isinstance(error, PaymasterError)
            assert isinstance(error, Exception)
    
    def test_retryable_inheritance(self):
        """Test RetryableError inheritance."""
        temp_error = TemporaryError("Test")
        
        assert isinstance(temp_error, RetryableError)
        assert isinstance(temp_error, PaymasterError)
        assert temp_error.details["retryable"] is True
    
    def test_permanent_error_inheritance(self):
        """Test PermanentError inheritance."""
        perm_error = PermanentError("Test")
        
        assert isinstance(perm_error, PaymasterError)
        assert not isinstance(perm_error, RetryableError)
        assert perm_error.details["retryable"] is False


class TestErrorSerialization:
    """Test error serialization for logging and monitoring."""
    
    def test_complex_error_serialization(self):
        """Test serialization of complex error with nested details."""
        details = {
            "context": "test_operation",
            "parameters": {"amount": 1000, "address": "0x123"},
            "metadata": {"attempt": 3, "timestamp": 1234567890}
        }
        
        error = DepositError("Processing failed", "deposit_123", "validation", details)
        error_dict = error.to_dict()
        
        assert error_dict["error_type"] == "DepositError"
        assert error_dict["message"] == "Processing failed"
        assert error_dict["error_code"] == "DEPOSIT_ERROR_VALIDATION"
        
        # Check that details are preserved
        assert error_dict["details"]["deposit_id"] == "deposit_123"
        assert error_dict["details"]["stage"] == "validation"
        assert error_dict["details"]["context"] == "test_operation"
        assert error_dict["details"]["parameters"]["amount"] == 1000
    
    def test_error_dict_json_serializable(self):
        """Test that error dict is JSON serializable."""
        import json
        
        error = Web3Error("RPC call failed", "eth_call", "0x123abc", {"gas": 21000})
        error_dict = error.to_dict()
        
        # Should not raise exception
        json_str = json.dumps(error_dict)
        parsed = json.loads(json_str)
        
        assert parsed["error_type"] == "Web3Error"
        assert parsed["details"]["gas"] == 21000