"""Data models and type definitions for the ROFL Cross-Chain Paymaster."""

import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from pydantic.types import StrictStr, StrictInt, StrictBool
from eth_typing import Address, HexStr
from web3.types import LogReceipt, TxReceipt


class DepositStatus(Enum):
    """Status of a deposit event."""
    
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class ProofStatus(Enum):
    """Status of proof generation."""
    
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    VERIFIED = "verified"
    FAILED = "failed"


class TransactionStatus(Enum):
    """Status of Sapphire transaction."""
    
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REVERTED = "reverted"


class DepositEvent(BaseModel):
    """Model for PaymasterDeposit event from Base vault contract."""
    
    
    # Event identification
    transaction_hash: StrictStr = Field(..., min_length=66, max_length=66)
    log_index: StrictInt = Field(..., ge=0)
    block_number: StrictInt = Field(..., gt=0)
    block_hash: StrictStr = Field(..., min_length=66, max_length=66)
    
    # Event data
    user_address: StrictStr = Field(..., min_length=42, max_length=42)
    deposit_amount: StrictStr = Field(...)  # Wei string to avoid precision loss
    recipient_address: StrictStr = Field(..., min_length=42, max_length=42)
    nonce: StrictInt = Field(..., ge=0)
    
    # Metadata
    timestamp: float = Field(default_factory=time.time)
    status: DepositStatus = Field(default=DepositStatus.PENDING)
    confirmation_count: StrictInt = Field(default=0, ge=0)
    
    # Processing tracking
    detected_at: float = Field(default_factory=time.time)
    confirmed_at: Optional[float] = None
    processed_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: StrictInt = Field(default=0, ge=0)
    last_retry_at: Optional[float] = None
    
    @field_validator('transaction_hash', 'block_hash')
    @classmethod
    def validate_hex_string(cls, v):
        """Validate hex strings start with 0x."""
        if not v.startswith('0x'):
            raise ValueError('Hex string must start with 0x')
        if not all(c in '0123456789abcdefABCDEF' for c in v[2:]):
            raise ValueError('Invalid hex characters')
        return v.lower()
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate status field - convert string to enum if needed."""
        if isinstance(v, str):
            return DepositStatus(v)
        return v
    
    @field_validator('user_address', 'recipient_address')
    @classmethod
    def validate_address(cls, v):
        """Validate Ethereum addresses."""
        if not v.startswith('0x'):
            raise ValueError('Address must start with 0x')
        if len(v) != 42:
            raise ValueError('Address must be 42 characters long')
        if not all(c in '0123456789abcdefABCDEF' for c in v[2:]):
            raise ValueError('Invalid hex characters in address')
        return v.lower()
    
    @field_validator('deposit_amount')
    @classmethod
    def validate_deposit_amount(cls, v):
        """Validate deposit amount is a valid wei string."""
        try:
            amount = int(v)
            if amount <= 0:
                raise ValueError('Deposit amount must be positive')
            # Check reasonable limits (0.01 USDC to 1M USDC in wei)
            min_amount = 10**4  # 0.01 USDC (6 decimals)
            max_amount = 10**12  # 1M USDC (6 decimals)
            if amount < min_amount or amount > max_amount:
                raise ValueError(f'Deposit amount outside reasonable bounds: {min_amount}-{max_amount}')
            return str(amount)
        except ValueError as e:
            if 'Deposit amount' in str(e):
                raise
            raise ValueError('Deposit amount must be a valid integer string')
    
    @field_validator('nonce')
    @classmethod
    def validate_nonce(cls, v):
        """Validate nonce is within reasonable bounds."""
        if v < 0:
            raise ValueError('Nonce must be non-negative')
        if v > 2**64 - 1:  # Reasonable upper bound
            raise ValueError('Nonce too large')
        return v
    
    @model_validator(mode='after')
    def validate_timestamps(self):
        """Validate timestamp ordering."""
        detected_at = self.detected_at
        confirmed_at = self.confirmed_at
        processed_at = self.processed_at
        completed_at = self.completed_at
        
        if confirmed_at and detected_at and confirmed_at < detected_at:
            raise ValueError('confirmed_at cannot be before detected_at')
        if processed_at and confirmed_at and processed_at < confirmed_at:
            raise ValueError('processed_at cannot be before confirmed_at')
        if completed_at and processed_at and completed_at < processed_at:
            raise ValueError('completed_at cannot be before processed_at')
            
        return self
    
    def get_deposit_amount_decimal(self) -> Decimal:
        """Get deposit amount as Decimal for precise calculations."""
        return Decimal(self.deposit_amount) / Decimal(10**6)  # USDC has 6 decimals
    
    def get_unique_id(self) -> str:
        """Get unique identifier for this deposit."""
        return f"{self.transaction_hash}:{self.log_index}"
    
    def is_expired(self, expiry_hours: int = 24) -> bool:
        """Check if deposit has expired."""
        if self.status == DepositStatus.COMPLETED:
            return False
        return time.time() - self.detected_at > expiry_hours * 3600
    
    def can_retry(self, max_retries: int = 3) -> bool:
        """Check if deposit can be retried."""
        return (
            self.status == DepositStatus.FAILED and
            self.retry_count < max_retries and
            not self.is_expired()
        )
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    )


class DepositProof(BaseModel):
    """Model for cryptographic proof data for cross-chain verification."""
    
    
    # Associated deposit
    deposit_id: StrictStr = Field(...)  # transaction_hash:log_index
    
    # Block data
    block_number: StrictInt = Field(..., gt=0)
    block_hash: StrictStr = Field(..., min_length=66, max_length=66)
    block_header_rlp: StrictStr = Field(...)  # RLP encoded block header
    
    # Transaction data
    transaction_hash: StrictStr = Field(..., min_length=66, max_length=66)
    transaction_index: StrictInt = Field(..., ge=0)
    transaction_rlp: StrictStr = Field(...)  # RLP encoded transaction
    
    # Receipt data
    receipt_rlp: StrictStr = Field(...)  # RLP encoded receipt
    receipt_index: StrictInt = Field(..., ge=0)
    
    # Merkle proofs
    transaction_proof: List[StrictStr] = Field(...)  # Merkle proof for transaction
    receipt_proof: List[StrictStr] = Field(...)     # Merkle proof for receipt
    
    # Log data
    log_index: StrictInt = Field(..., ge=0)
    log_data: StrictStr = Field(...)  # RLP encoded log entry
    
    # Proof metadata
    generated_at: float = Field(default_factory=time.time)
    status: ProofStatus = Field(default=ProofStatus.PENDING)
    generation_time: Optional[float] = None  # Time taken to generate proof
    
    # Validation data
    verified_at: Optional[float] = None
    verification_result: Optional[bool] = None
    verification_error: Optional[str] = None
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate status field - convert string to enum if needed."""
        if isinstance(v, str):
            return ProofStatus(v)
        return v
    
    @field_validator('block_hash', 'transaction_hash')
    @classmethod
    def validate_hex_strings(cls, v):
        """Validate hex strings."""
        if not v.startswith('0x'):
            raise ValueError('Hex string must start with 0x')
        if not all(c in '0123456789abcdefABCDEF' for c in v[2:]):
            raise ValueError('Invalid hex characters')
        return v.lower()
    
    @field_validator('block_header_rlp', 'transaction_rlp', 'receipt_rlp', 'log_data')
    @classmethod
    def validate_rlp_data(cls, v):
        """Validate RLP encoded data."""
        if not v.startswith('0x'):
            raise ValueError('RLP data must start with 0x')
        if len(v) < 4:  # At least 0x + 1 byte
            raise ValueError('RLP data too short')
        if not all(c in '0123456789abcdefABCDEF' for c in v[2:]):
            raise ValueError('Invalid hex characters in RLP data')
        return v.lower()
    
    @field_validator('transaction_proof', 'receipt_proof')
    @classmethod
    def validate_merkle_proofs(cls, v):
        """Validate Merkle proof arrays."""
        if not v:
            raise ValueError('Merkle proof cannot be empty')
        for i, proof_element in enumerate(v):
            if not proof_element.startswith('0x'):
                raise ValueError(f'Proof element {i} must start with 0x')
            if len(proof_element) != 66:  # 32 bytes = 64 hex chars + 0x
                raise ValueError(f'Proof element {i} must be 32 bytes')
            if not all(c in '0123456789abcdefABCDEF' for c in proof_element[2:]):
                raise ValueError(f'Invalid hex characters in proof element {i}')
        return [p.lower() for p in v]
    
    @field_validator('generation_time')
    @classmethod
    def validate_generation_time(cls, v):
        """Validate generation time is reasonable."""
        if v is not None:
            if v < 0:
                raise ValueError('Generation time cannot be negative')
            if v > 300:  # 5 minutes seems reasonable maximum
                raise ValueError('Generation time too long')
        return v
    
    def get_proof_size(self) -> int:
        """Get total size of proof data in bytes."""
        size = 0
        size += len(self.block_header_rlp) // 2 - 1  # Remove 0x prefix
        size += len(self.transaction_rlp) // 2 - 1
        size += len(self.receipt_rlp) // 2 - 1
        size += len(self.log_data) // 2 - 1
        size += sum(len(p) // 2 - 1 for p in self.transaction_proof)
        size += sum(len(p) // 2 - 1 for p in self.receipt_proof)
        return size
    
    def is_valid(self) -> bool:
        """Check if proof is valid and ready for submission."""
        return (
            self.status == ProofStatus.GENERATED and
            self.verification_result is True and
            self.generation_time is not None and
            self.generation_time < 60.0  # Generated within 1 minute
        )
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        }
    )


class PriceData(BaseModel):
    """Model for USDC/ROSE price data from oracle."""
    
    # Price information
    usdc_to_rose_rate: StrictStr = Field(...)  # Rate as string to avoid precision loss
    rose_to_usdc_rate: StrictStr = Field(...)  # Inverse rate
    
    # Oracle metadata
    oracle_timestamp: StrictInt = Field(..., gt=0)
    oracle_block_number: StrictInt = Field(..., gt=0)
    oracle_address: StrictStr = Field(..., min_length=42, max_length=42)
    
    # Fetching metadata
    fetched_at: float = Field(default_factory=time.time)
    cache_expires_at: float = Field(...)
    
    # Validation data
    is_stale: StrictBool = Field(default=False)
    staleness_threshold: StrictInt = Field(default=3600)  # 1 hour in seconds
    
    @field_validator('usdc_to_rose_rate', 'rose_to_usdc_rate')
    @classmethod
    def validate_rates(cls, v):
        """Validate price rates."""
        try:
            rate = Decimal(v)
            if rate <= 0:
                raise ValueError('Price rate must be positive')
            if rate > Decimal('1000000'):  # Reasonable upper bound
                raise ValueError('Price rate too high')
            return str(rate)
        except (ValueError, ArithmeticError) as e:
            if 'Price rate' in str(e):
                raise
            raise ValueError('Invalid price rate format')
    
    @field_validator('oracle_address')
    @classmethod
    def validate_oracle_address(cls, v):
        """Validate oracle contract address."""
        if not v.startswith('0x'):
            raise ValueError('Oracle address must start with 0x')
        if len(v) != 42:
            raise ValueError('Oracle address must be 42 characters long')
        if not all(c in '0123456789abcdefABCDEF' for c in v[2:]):
            raise ValueError('Invalid hex characters in oracle address')
        return v.lower()
    
    @model_validator(mode='after')
    def validate_staleness(self):
        """Validate staleness calculation."""
        oracle_timestamp = self.oracle_timestamp
        fetched_at = self.fetched_at
        staleness_threshold = self.staleness_threshold
        
        if oracle_timestamp and fetched_at:
            age = fetched_at - oracle_timestamp
            # Use object.__setattr__ to avoid triggering validation recursion
            object.__setattr__(self, 'is_stale', age > staleness_threshold)
            
        return self
    
    def get_usdc_to_rose_decimal(self) -> Decimal:
        """Get USDC to ROSE rate as Decimal."""
        return Decimal(self.usdc_to_rose_rate)
    
    def get_rose_to_usdc_decimal(self) -> Decimal:
        """Get ROSE to USDC rate as Decimal."""
        return Decimal(self.rose_to_usdc_rate)
    
    def calculate_rose_amount(self, usdc_amount: Union[str, Decimal]) -> Decimal:
        """Calculate ROSE amount for given USDC amount."""
        if isinstance(usdc_amount, str):
            usdc_amount = Decimal(usdc_amount)
        return usdc_amount * self.get_usdc_to_rose_decimal()
    
    def calculate_usdc_amount(self, rose_amount: Union[str, Decimal]) -> Decimal:
        """Calculate USDC amount for given ROSE amount."""
        if isinstance(rose_amount, str):
            rose_amount = Decimal(rose_amount)
        return rose_amount * self.get_rose_to_usdc_decimal()
    
    def is_expired(self) -> bool:
        """Check if cached price data has expired."""
        return time.time() > self.cache_expires_at
    
    def apply_slippage_protection(self, rate: Decimal, slippage_percent: Decimal = Decimal('0.5')) -> Decimal:
        """Apply slippage protection to rate."""
        slippage_multiplier = (Decimal('100') - slippage_percent) / Decimal('100')
        return rate * slippage_multiplier
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    )


class ProcessingState(BaseModel):
    """Model for tracking deposit processing state."""
    
    
    # Deposit reference
    deposit_id: StrictStr = Field(...)
    deposit_event: DepositEvent = Field(...)
    
    # Processing components
    proof_data: Optional[DepositProof] = None
    price_data: Optional[PriceData] = None
    
    # Transaction data
    sapphire_tx_hash: Optional[StrictStr] = None
    sapphire_tx_status: TransactionStatus = Field(default=TransactionStatus.PENDING)
    sapphire_block_number: Optional[StrictInt] = None
    sapphire_gas_used: Optional[StrictInt] = None
    
    # Processing metadata
    processing_started_at: float = Field(default_factory=time.time)
    processing_completed_at: Optional[float] = None
    total_processing_time: Optional[float] = None
    
    # Error handling
    last_error: Optional[str] = None
    error_count: StrictInt = Field(default=0, ge=0)
    
    @field_validator('sapphire_tx_status')
    @classmethod
    def validate_tx_status(cls, v):
        """Validate sapphire_tx_status field - convert string to enum if needed."""
        if isinstance(v, str):
            return TransactionStatus(v)
        return v
    
    @field_validator('sapphire_tx_hash')
    @classmethod
    def validate_tx_hash(cls, v):
        """Validate Sapphire transaction hash."""
        if v is not None:
            if not v.startswith('0x'):
                raise ValueError('Transaction hash must start with 0x')
            if len(v) != 66:
                raise ValueError('Transaction hash must be 66 characters long')
            if not all(c in '0123456789abcdefABCDEF' for c in v[2:]):
                raise ValueError('Invalid hex characters in transaction hash')
            return v.lower()
        return v
    
    def is_complete(self) -> bool:
        """Check if processing is complete."""
        return (
            self.sapphire_tx_status == TransactionStatus.CONFIRMED and
            self.processing_completed_at is not None
        )
    
    def is_failed(self) -> bool:
        """Check if processing has failed."""
        return (
            self.sapphire_tx_status in (TransactionStatus.FAILED, TransactionStatus.REVERTED) or
            self.deposit_event.status == DepositStatus.FAILED
        )
    
    def get_processing_duration(self) -> Optional[float]:
        """Get processing duration in seconds."""
        if self.processing_completed_at:
            return self.processing_completed_at - self.processing_started_at
        return None
    
    def update_completion(self) -> None:
        """Update completion timestamp and duration."""
        self.processing_completed_at = time.time()
        self.total_processing_time = self.get_processing_duration()
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    )