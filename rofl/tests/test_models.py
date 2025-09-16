"""Tests for data models and type definitions."""

import pytest
import time
from decimal import Decimal
from datetime import datetime
from pydantic import ValidationError

from rofl_paymaster.models import (
    DepositEvent, DepositProof, PriceData, ProcessingState,
    DepositStatus, ProofStatus, TransactionStatus
)
from rofl_paymaster.exceptions import ValidationError as PaymasterValidationError


class TestDepositEvent:
    """Test DepositEvent model."""
    
    def test_deposit_event_valid_creation(self):
        """Test creating a valid deposit event."""
        event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",  # 1 USDC
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1
        )
        
        assert event.status == DepositStatus.PENDING
        assert event.confirmation_count == 0
        assert event.retry_count == 0
        assert event.get_unique_id() == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef:0"
        assert event.get_deposit_amount_decimal() == Decimal("1.000000")
    
    def test_deposit_event_validation_errors(self):
        """Test deposit event validation errors."""
        # Invalid transaction hash (too short)
        with pytest.raises(ValidationError, match="String should have at least 66 characters"):
            DepositEvent(
                transaction_hash="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                log_index=0,
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="1000000",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=1
            )
        
        # Invalid address length (actually too short)
        with pytest.raises(ValidationError, match="String should have at least 42 characters"):
            DepositEvent(
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                log_index=0,
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a8",  # Actually too short (40 chars total)
                deposit_amount="1000000",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=1
            )
        
        # Invalid deposit amount
        with pytest.raises(ValueError, match="Deposit amount must be positive"):
            DepositEvent(
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                log_index=0,
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="0",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=1
            )
        
        # Deposit amount too small
        with pytest.raises(ValueError, match="Deposit amount outside reasonable bounds"):
            DepositEvent(
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                log_index=0,
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="100",  # 0.0001 USDC - too small
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=1
            )
    
    def test_deposit_event_timestamp_validation(self):
        """Test timestamp ordering validation."""
        base_time = time.time()
        
        # Invalid: confirmed_at before detected_at
        with pytest.raises(ValueError, match="confirmed_at cannot be before detected_at"):
            DepositEvent(
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                log_index=0,
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="1000000",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=1,
                detected_at=base_time,
                confirmed_at=base_time - 100
            )
    
    def test_deposit_event_expiry(self):
        """Test deposit expiry logic."""
        old_time = time.time() - 25 * 3600  # 25 hours ago
        
        event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1,
            detected_at=old_time
        )
        
        assert event.is_expired()
        assert not event.is_expired(expiry_hours=48)  # Within 48 hours
        
        # Completed events should not be considered expired
        event.status = DepositStatus.COMPLETED
        assert not event.is_expired()
    
    def test_deposit_event_retry_logic(self):
        """Test retry logic."""
        event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1,
            status=DepositStatus.FAILED,
            retry_count=1
        )
        
        assert event.can_retry()
        
        # Too many retries
        event.retry_count = 5
        assert not event.can_retry()
        
        # Expired event
        event.retry_count = 1
        event.detected_at = time.time() - 25 * 3600
        assert not event.can_retry()


class TestDepositProof:
    """Test DepositProof model."""
    
    def test_deposit_proof_valid_creation(self):
        """Test creating a valid deposit proof."""
        proof = DepositProof(
            deposit_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef:0",
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            block_header_rlp="0xf90211a0abcdef",
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            transaction_index=0,
            transaction_rlp="0xf86d8086",
            receipt_rlp="0xf901118086",
            receipt_index=0,
            transaction_proof=["0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"],
            receipt_proof=["0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"],
            log_index=0,
            log_data="0xf90211a0"
        )
        
        assert proof.status == ProofStatus.PENDING
        assert proof.verification_result is None
        assert proof.get_proof_size() > 0
    
    def test_deposit_proof_validation_errors(self):
        """Test deposit proof validation errors."""
        # Invalid Merkle proof (not 32 bytes)
        with pytest.raises(ValueError, match="Proof element 0 must be 32 bytes"):
            DepositProof(
                deposit_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef:0",
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                block_header_rlp="0xf90211a0abcdef",
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                transaction_index=0,
                transaction_rlp="0xf86d8086",
                receipt_rlp="0xf901118086",
                receipt_index=0,
                transaction_proof=["0x1234"],  # Too short
                receipt_proof=["0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"],
                log_index=0,
                log_data="0xf90211a0"
            )
        
        # Empty Merkle proof
        with pytest.raises(ValueError, match="Merkle proof cannot be empty"):
            DepositProof(
                deposit_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef:0",
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                block_header_rlp="0xf90211a0abcdef",
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                transaction_index=0,
                transaction_rlp="0xf86d8086",
                receipt_rlp="0xf901118086",
                receipt_index=0,
                transaction_proof=[],  # Empty
                receipt_proof=["0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"],
                log_index=0,
                log_data="0xf90211a0"
            )
        
        # Invalid generation time
        with pytest.raises(ValueError, match="Generation time too long"):
            DepositProof(
                deposit_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef:0",
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                block_header_rlp="0xf90211a0abcdef",
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                transaction_index=0,
                transaction_rlp="0xf86d8086",
                receipt_rlp="0xf901118086",
                receipt_index=0,
                transaction_proof=["0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"],
                receipt_proof=["0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"],
                log_index=0,
                log_data="0xf90211a0",
                generation_time=400.0  # Too long
            )
    
    def test_deposit_proof_validity(self):
        """Test proof validity checking."""
        proof = DepositProof(
            deposit_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef:0",
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            block_header_rlp="0xf90211a0abcdef",
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            transaction_index=0,
            transaction_rlp="0xf86d8086",
            receipt_rlp="0xf901118086",
            receipt_index=0,
            transaction_proof=["0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"],
            receipt_proof=["0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"],
            log_index=0,
            log_data="0xf90211a0",
            status=ProofStatus.GENERATED,
            verification_result=True,
            generation_time=30.0
        )
        
        assert proof.is_valid()
        
        # Invalid if verification failed
        proof.verification_result = False
        assert not proof.is_valid()
        
        # Invalid if generation took too long
        proof.verification_result = True
        proof.generation_time = 120.0
        assert not proof.is_valid()


class TestPriceData:
    """Test PriceData model."""
    
    def test_price_data_valid_creation(self):
        """Test creating valid price data."""
        current_time = time.time()
        
        price_data = PriceData(
            usdc_to_rose_rate="0.15",
            rose_to_usdc_rate="6.666667",
            oracle_timestamp=int(current_time),
            oracle_block_number=12345,
            oracle_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            cache_expires_at=current_time + 300
        )
        
        assert price_data.get_usdc_to_rose_decimal() == Decimal("0.15")
        assert price_data.get_rose_to_usdc_decimal() == Decimal("6.666667")
        assert not price_data.is_expired()
        assert not price_data.is_stale
    
    def test_price_data_calculations(self):
        """Test price calculations."""
        price_data = PriceData(
            usdc_to_rose_rate="0.15",
            rose_to_usdc_rate="6.666667",
            oracle_timestamp=int(time.time()),
            oracle_block_number=12345,
            oracle_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            cache_expires_at=time.time() + 300
        )
        
        # Test USDC to ROSE conversion
        rose_amount = price_data.calculate_rose_amount(Decimal("100"))
        assert rose_amount == Decimal("15.0")
        
        # Test ROSE to USDC conversion
        usdc_amount = price_data.calculate_usdc_amount(Decimal("15"))
        assert usdc_amount == Decimal("100.000005")  # 15 * 6.666667
        
        # Test slippage protection
        protected_rate = price_data.apply_slippage_protection(Decimal("0.15"), Decimal("0.5"))
        assert protected_rate == Decimal("0.14925")  # 0.15 * 0.995
    
    def test_price_data_validation_errors(self):
        """Test price data validation errors."""
        # Invalid rate (negative)
        with pytest.raises(ValueError, match="Price rate must be positive"):
            PriceData(
                usdc_to_rose_rate="-0.15",
                rose_to_usdc_rate="6.666667",
                oracle_timestamp=int(time.time()),
                oracle_block_number=12345,
                oracle_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                cache_expires_at=time.time() + 300
            )
        
        # Invalid oracle address (too short)
        with pytest.raises(ValidationError, match="String should have at least 42 characters"):
            PriceData(
                usdc_to_rose_rate="0.15",
                rose_to_usdc_rate="6.666667",
                oracle_timestamp=int(time.time()),
                oracle_block_number=12345,
                oracle_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a8",  # Actually too short (40 chars total)
                cache_expires_at=time.time() + 300
            )
    
    def test_price_data_staleness(self):
        """Test price staleness detection."""
        old_time = time.time() - 7200  # 2 hours ago
        
        price_data = PriceData(
            usdc_to_rose_rate="0.15",
            rose_to_usdc_rate="6.666667",
            oracle_timestamp=int(old_time),
            oracle_block_number=12345,
            oracle_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            cache_expires_at=time.time() + 300,
            staleness_threshold=3600  # 1 hour
        )
        
        assert price_data.is_stale
    
    def test_price_data_expiry(self):
        """Test price data expiry."""
        price_data = PriceData(
            usdc_to_rose_rate="0.15",
            rose_to_usdc_rate="6.666667",
            oracle_timestamp=int(time.time()),
            oracle_block_number=12345,
            oracle_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            cache_expires_at=time.time() - 100  # Expired 100 seconds ago
        )
        
        assert price_data.is_expired()


class TestProcessingState:
    """Test ProcessingState model."""
    
    def test_processing_state_valid_creation(self):
        """Test creating valid processing state."""
        deposit_event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1
        )
        
        state = ProcessingState(
            deposit_id=deposit_event.get_unique_id(),
            deposit_event=deposit_event
        )
        
        assert state.sapphire_tx_status == TransactionStatus.PENDING
        assert state.error_count == 0
        assert not state.is_complete()
        assert not state.is_failed()
    
    def test_processing_state_completion(self):
        """Test processing state completion."""
        deposit_event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1
        )
        
        state = ProcessingState(
            deposit_id=deposit_event.get_unique_id(),
            deposit_event=deposit_event,
            sapphire_tx_status=TransactionStatus.CONFIRMED
        )
        
        state.update_completion()
        
        assert state.is_complete()
        assert state.processing_completed_at is not None
        assert state.total_processing_time is not None
        assert state.get_processing_duration() is not None
    
    def test_processing_state_failure(self):
        """Test processing state failure detection."""
        deposit_event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1,
            status=DepositStatus.FAILED
        )
        
        state = ProcessingState(
            deposit_id=deposit_event.get_unique_id(),
            deposit_event=deposit_event
        )
        
        assert state.is_failed()
        
        # Test Sapphire transaction failure
        deposit_event.status = DepositStatus.PROCESSING
        state.sapphire_tx_status = TransactionStatus.FAILED
        assert state.is_failed()
    
    def test_processing_state_tx_hash_validation(self):
        """Test Sapphire transaction hash validation."""
        deposit_event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1
        )
        
        # Valid transaction hash
        state = ProcessingState(
            deposit_id=deposit_event.get_unique_id(),
            deposit_event=deposit_event,
            sapphire_tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        )
        
        assert state.sapphire_tx_hash == "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        
        # Invalid transaction hash
        with pytest.raises(ValueError, match="Transaction hash must be 66 characters long"):
            ProcessingState(
                deposit_id=deposit_event.get_unique_id(),
                deposit_event=deposit_event,
                sapphire_tx_hash="0xabcdef"  # Too short
            )


class TestEnumValues:
    """Test enum value serialization."""
    
    def test_deposit_status_values(self):
        """Test DepositStatus enum values."""
        assert DepositStatus.PENDING.value == "pending"
        assert DepositStatus.CONFIRMED.value == "confirmed"
        assert DepositStatus.PROCESSING.value == "processing"
        assert DepositStatus.COMPLETED.value == "completed"
        assert DepositStatus.FAILED.value == "failed"
        assert DepositStatus.EXPIRED.value == "expired"
    
    def test_proof_status_values(self):
        """Test ProofStatus enum values."""
        assert ProofStatus.PENDING.value == "pending"
        assert ProofStatus.GENERATING.value == "generating"
        assert ProofStatus.GENERATED.value == "generated"
        assert ProofStatus.VERIFIED.value == "verified"
        assert ProofStatus.FAILED.value == "failed"
    
    def test_transaction_status_values(self):
        """Test TransactionStatus enum values."""
        assert TransactionStatus.PENDING.value == "pending"
        assert TransactionStatus.SUBMITTED.value == "submitted"
        assert TransactionStatus.CONFIRMED.value == "confirmed"
        assert TransactionStatus.FAILED.value == "failed"
        assert TransactionStatus.REVERTED.value == "reverted"


class TestModelSerialization:
    """Test model JSON serialization."""
    
    def test_deposit_event_serialization(self):
        """Test DepositEvent JSON serialization."""
        event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1
        )
        
        # Test JSON serialization
        json_str = event.model_dump_json()
        assert "transaction_hash" in json_str
        assert "pending" in json_str  # Status value
        
        # Test deserialization
        event_copy = DepositEvent.model_validate_json(json_str)
        assert event_copy.transaction_hash == event.transaction_hash
        # Status should be properly deserialized as enum
        assert event_copy.status == DepositStatus.PENDING
    
    def test_deposit_proof_serialization(self):
        """Test DepositProof JSON serialization."""
        proof = DepositProof(
            deposit_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef:0",
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            block_header_rlp="0xf90211a0abcdef",
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            transaction_index=0,
            transaction_rlp="0xf86d8086",
            receipt_rlp="0xf901118086",
            receipt_index=0,
            transaction_proof=["0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"],
            receipt_proof=["0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"],
            log_index=0,
            log_data="0xf90211a0"
        )
        
        # Test JSON serialization
        json_str = proof.model_dump_json()
        assert "deposit_id" in json_str
        assert "transaction_proof" in json_str
        
        # Test deserialization
        proof_copy = DepositProof.model_validate_json(json_str)
        assert proof_copy.deposit_id == proof.deposit_id
        assert proof_copy.transaction_proof == proof.transaction_proof