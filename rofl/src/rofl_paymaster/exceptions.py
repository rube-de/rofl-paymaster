"""Custom exception classes for the ROFL Cross-Chain Paymaster."""

from typing import Optional, Dict, Any


class PaymasterError(Exception):
    """Base exception for all paymaster errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize paymaster error.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
        }


class ConfigurationError(PaymasterError):
    """Raised when there are configuration issues."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize configuration error.
        
        Args:
            message: Error description
            config_key: Configuration key that caused the error
            details: Additional context
        """
        error_code = f"CONFIG_ERROR_{config_key.upper()}" if config_key else "CONFIG_ERROR"
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        
        super().__init__(message, error_code, details)


class ConnectionError(PaymasterError):
    """Raised when there are connection issues."""
    
    def __init__(self, message: str, provider_url: Optional[str] = None, chain_id: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize connection error.
        
        Args:
            message: Error description
            provider_url: RPC provider URL that failed
            chain_id: Chain ID being connected to
            details: Additional context
        """
        error_code = "CONNECTION_ERROR"
        details = details or {}
        if provider_url:
            details["provider_url"] = provider_url
        if chain_id:
            details["chain_id"] = chain_id
        
        super().__init__(message, error_code, details)


class Web3Error(PaymasterError):
    """Raised when there are Web3 interaction errors."""
    
    def __init__(self, message: str, method: Optional[str] = None, transaction_hash: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize Web3 error.
        
        Args:
            message: Error description
            method: Web3 method that failed
            transaction_hash: Transaction hash if applicable
            details: Additional context
        """
        error_code = f"WEB3_ERROR_{method.upper()}" if method else "WEB3_ERROR"
        details = details or {}
        if method:
            details["method"] = method
        if transaction_hash:
            details["transaction_hash"] = transaction_hash
        
        super().__init__(message, error_code, details)


class DepositError(PaymasterError):
    """Raised when there are deposit processing errors."""
    
    def __init__(self, message: str, deposit_id: Optional[str] = None, stage: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize deposit error.
        
        Args:
            message: Error description
            deposit_id: Unique deposit identifier
            stage: Processing stage where error occurred
            details: Additional context
        """
        error_code = f"DEPOSIT_ERROR_{stage.upper()}" if stage else "DEPOSIT_ERROR"
        details = details or {}
        if deposit_id:
            details["deposit_id"] = deposit_id
        if stage:
            details["stage"] = stage
        
        super().__init__(message, error_code, details)


class ProofGenerationError(PaymasterError):
    """Raised when proof generation fails."""
    
    def __init__(self, message: str, block_number: Optional[int] = None, transaction_hash: Optional[str] = None, proof_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize proof generation error.
        
        Args:
            message: Error description
            block_number: Block number being processed
            transaction_hash: Transaction hash being processed
            proof_type: Type of proof being generated
            details: Additional context
        """
        error_code = f"PROOF_ERROR_{proof_type.upper()}" if proof_type else "PROOF_ERROR"
        details = details or {}
        if block_number:
            details["block_number"] = block_number
        if transaction_hash:
            details["transaction_hash"] = transaction_hash
        if proof_type:
            details["proof_type"] = proof_type
        
        super().__init__(message, error_code, details)


class ValidationError(PaymasterError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize validation error.
        
        Args:
            message: Error description
            field: Field that failed validation
            value: Value that failed validation
            details: Additional context
        """
        error_code = f"VALIDATION_ERROR_{field.upper()}" if field else "VALIDATION_ERROR"
        details = details or {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        
        super().__init__(message, error_code, details)


class PriceOracleError(PaymasterError):
    """Raised when price oracle operations fail."""
    
    def __init__(self, message: str, oracle_address: Optional[str] = None, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize price oracle error.
        
        Args:
            message: Error description
            oracle_address: Oracle contract address
            operation: Oracle operation that failed
            details: Additional context
        """
        error_code = f"ORACLE_ERROR_{operation.upper()}" if operation else "ORACLE_ERROR"
        details = details or {}
        if oracle_address:
            details["oracle_address"] = oracle_address
        if operation:
            details["operation"] = operation
        
        super().__init__(message, error_code, details)


class TransactionError(PaymasterError):
    """Raised when transaction operations fail."""
    
    def __init__(self, message: str, transaction_hash: Optional[str] = None, nonce: Optional[int] = None, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize transaction error.
        
        Args:
            message: Error description
            transaction_hash: Transaction hash
            nonce: Transaction nonce
            operation: Transaction operation that failed
            details: Additional context
        """
        error_code = f"TX_ERROR_{operation.upper()}" if operation else "TX_ERROR"
        details = details or {}
        if transaction_hash:
            details["transaction_hash"] = transaction_hash
        if nonce is not None:
            details["nonce"] = nonce
        if operation:
            details["operation"] = operation
        
        super().__init__(message, error_code, details)


class EventMonitoringError(PaymasterError):
    """Raised when event monitoring fails."""
    
    def __init__(self, message: str, contract_address: Optional[str] = None, event_signature: Optional[str] = None, block_range: Optional[tuple] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize event monitoring error.
        
        Args:
            message: Error description
            contract_address: Contract being monitored
            event_signature: Event signature being monitored
            block_range: Block range being processed
            details: Additional context
        """
        error_code = "EVENT_MONITORING_ERROR"
        details = details or {}
        if contract_address:
            details["contract_address"] = contract_address
        if event_signature:
            details["event_signature"] = event_signature
        if block_range:
            details["block_range"] = block_range
        
        super().__init__(message, error_code, details)


class BlockhashOracleError(PaymasterError):
    """Raised when blockhash oracle operations fail."""
    
    def __init__(self, message: str, oracle_address: Optional[str] = None, block_number: Optional[int] = None, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize blockhash oracle error.
        
        Args:
            message: Error description
            oracle_address: Oracle contract address
            block_number: Block number being processed
            operation: Oracle operation that failed
            details: Additional context
        """
        error_code = f"BLOCKHASH_ERROR_{operation.upper()}" if operation else "BLOCKHASH_ERROR"
        details = details or {}
        if oracle_address:
            details["oracle_address"] = oracle_address
        if block_number:
            details["block_number"] = block_number
        if operation:
            details["operation"] = operation
        
        super().__init__(message, error_code, details)


class SecurityError(PaymasterError):
    """Raised when security violations are detected."""
    
    def __init__(self, message: str, violation_type: Optional[str] = None, severity: str = "high", details: Optional[Dict[str, Any]] = None):
        """Initialize security error.
        
        Args:
            message: Error description
            violation_type: Type of security violation
            severity: Severity level (low, medium, high, critical)
            details: Additional context
        """
        error_code = f"SECURITY_ERROR_{violation_type.upper()}" if violation_type else "SECURITY_ERROR"
        details = details or {}
        details["severity"] = severity
        if violation_type:
            details["violation_type"] = violation_type
        
        super().__init__(message, error_code, details)


class RateLimitError(PaymasterError):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, message: str, limit_type: Optional[str] = None, retry_after: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize rate limit error.
        
        Args:
            message: Error description
            limit_type: Type of rate limit exceeded
            retry_after: Seconds to wait before retry
            details: Additional context
        """
        error_code = f"RATE_LIMIT_{limit_type.upper()}" if limit_type else "RATE_LIMIT_ERROR"
        details = details or {}
        if limit_type:
            details["limit_type"] = limit_type
        if retry_after:
            details["retry_after"] = retry_after
        
        super().__init__(message, error_code, details)


class CircuitBreakerError(PaymasterError):
    """Raised when circuit breaker is open."""
    
    def __init__(self, message: str, service: Optional[str] = None, failure_rate: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize circuit breaker error.
        
        Args:
            message: Error description
            service: Service with open circuit breaker
            failure_rate: Current failure rate
            details: Additional context
        """
        error_code = f"CIRCUIT_BREAKER_{service.upper()}" if service else "CIRCUIT_BREAKER_ERROR"
        details = details or {}
        if service:
            details["service"] = service
        if failure_rate:
            details["failure_rate"] = failure_rate
        
        super().__init__(message, error_code, details)


class RetryableError(PaymasterError):
    """Base class for errors that can be retried."""
    
    def __init__(self, message: str, retry_after: Optional[float] = None, max_retries: int = 3, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize retryable error.
        
        Args:
            message: Error description
            retry_after: Seconds to wait before retry
            max_retries: Maximum number of retries
            error_code: Machine-readable error code
            details: Additional context
        """
        details = details or {}
        details["retry_after"] = retry_after
        details["max_retries"] = max_retries
        details["retryable"] = True
        
        super().__init__(message, error_code, details)


class TemporaryError(RetryableError):
    """Raised for temporary errors that should be retried."""
    
    def __init__(self, message: str, service: Optional[str] = None, retry_after: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize temporary error.
        
        Args:
            message: Error description
            service: Service that is temporarily unavailable
            retry_after: Seconds to wait before retry
            details: Additional context
        """
        error_code = f"TEMPORARY_ERROR_{service.upper()}" if service else "TEMPORARY_ERROR"
        details = details or {}
        if service:
            details["service"] = service
        
        super().__init__(message, retry_after, error_code=error_code, details=details)


class PermanentError(PaymasterError):
    """Raised for permanent errors that should not be retried."""
    
    def __init__(self, message: str, reason: Optional[str] = None, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize permanent error.
        
        Args:
            message: Error description
            reason: Reason why error is permanent
            error_code: Machine-readable error code
            details: Additional context
        """
        details = details or {}
        details["retryable"] = False
        if reason:
            details["reason"] = reason
        
        error_code = error_code or "PERMANENT_ERROR"
        super().__init__(message, error_code, details)


# Utility functions for error handling

def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable."""
    if isinstance(error, RetryableError):
        return True
    if isinstance(error, PermanentError):
        return False
    
    # Default heuristics for common errors
    if isinstance(error, (ConnectionError, TemporaryError, RateLimitError)):
        return True
    if isinstance(error, (ValidationError, SecurityError, ConfigurationError)):
        return False
    
    return False


def get_retry_delay(error: Exception, attempt: int = 1, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Get retry delay for an error."""
    if isinstance(error, RetryableError) and error.details.get("retry_after"):
        return float(error.details["retry_after"])
    
    # Exponential backoff with jitter
    import random
    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
    jitter = random.uniform(0.1, 0.3) * delay
    return delay + jitter


def categorize_error(error: Exception) -> str:
    """Categorize an error for monitoring and alerting."""
    if isinstance(error, SecurityError):
        return "security"
    elif isinstance(error, ConnectionError):
        return "connectivity"
    elif isinstance(error, ConfigurationError):
        return "configuration"
    elif isinstance(error, ValidationError):
        return "validation"
    elif isinstance(error, ProofGenerationError):
        return "proof_generation"
    elif isinstance(error, TransactionError):
        return "transaction"
    elif isinstance(error, EventMonitoringError):
        return "event_monitoring"
    elif isinstance(error, PriceOracleError):
        return "price_oracle"
    elif isinstance(error, BlockhashOracleError):
        return "blockhash_oracle"
    elif isinstance(error, RateLimitError):
        return "rate_limiting"
    elif isinstance(error, CircuitBreakerError):
        return "circuit_breaker"
    elif isinstance(error, TemporaryError):
        return "temporary"
    elif isinstance(error, PermanentError):
        return "permanent"
    else:
        return "unknown"