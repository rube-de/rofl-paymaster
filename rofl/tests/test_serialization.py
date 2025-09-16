"""Tests for serialization and deserialization utilities."""

import pytest
import json
import os
import tempfile
import time
from pathlib import Path
from decimal import Decimal

from rofl_paymaster.models import (
    DepositEvent, DepositProof, PriceData, ProcessingState,
    DepositStatus, ProofStatus, TransactionStatus
)
from rofl_paymaster.serialization import (
    ModelSerializer, FileSerializer, StateManager,
    serialize_model_list, deserialize_model_list,
    create_model_snapshot, restore_model_from_snapshot
)
from rofl_paymaster.exceptions import ValidationError as PaymasterValidationError


def assert_status_equal(actual_status, expected_status):
    """Helper function to compare status values that might be enums or strings."""
    if hasattr(actual_status, 'value'):
        actual_value = actual_status.value
    else:
        actual_value = actual_status
    
    if hasattr(expected_status, 'value'):
        expected_value = expected_status.value
    else:
        expected_value = expected_status
    
    assert actual_value == expected_value


class TestModelSerializer:
    """Test ModelSerializer class."""
    
    def test_serialize_to_json(self):
        """Test model serialization to JSON."""
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
        
        json_str = ModelSerializer.serialize_to_json(event)
        
        assert isinstance(json_str, str)
        assert "transaction_hash" in json_str
        assert "0x1234567890abcdef" in json_str
        assert "pending" in json_str  # Status enum value
    
    def test_serialize_to_json_with_indent(self):
        """Test JSON serialization with indentation."""
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
        
        json_str = ModelSerializer.serialize_to_json(event, indent=2)
        
        # Should contain newlines and indentation
        assert "\n" in json_str
        assert "  " in json_str
    
    def test_deserialize_from_json(self):
        """Test model deserialization from JSON."""
        original_event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1
        )
        
        json_str = ModelSerializer.serialize_to_json(original_event)
        deserialized_event = ModelSerializer.deserialize_from_json(json_str, DepositEvent)
        
        assert deserialized_event.transaction_hash == original_event.transaction_hash
        assert deserialized_event.block_number == original_event.block_number
        # Status can be either enum or string value after deserialization
        if hasattr(deserialized_event.status, 'value'):
            assert deserialized_event.status.value == original_event.status.value
        else:
            assert deserialized_event.status == original_event.status.value
        assert deserialized_event.deposit_amount == original_event.deposit_amount
    
    def test_deserialize_from_json_invalid(self):
        """Test deserialization error handling."""
        invalid_json = '{"transaction_hash": "invalid_hash"}'  # Missing required fields
        
        with pytest.raises(PaymasterValidationError) as exc_info:
            ModelSerializer.deserialize_from_json(invalid_json, DepositEvent)
        
        assert "Failed to deserialize JSON to DepositEvent" in str(exc_info.value)
        assert "validation_errors" in exc_info.value.details
    
    def test_serialize_to_dict(self):
        """Test model serialization to dictionary."""
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
        
        data_dict = ModelSerializer.serialize_to_dict(event)
        
        assert isinstance(data_dict, dict)
        assert data_dict["transaction_hash"] == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        assert data_dict["block_number"] == 12345
        assert data_dict["status"] == "pending"
    
    def test_serialize_to_dict_exclude_none(self):
        """Test dictionary serialization excluding None values."""
        event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1,
            confirmed_at=None  # This should be excluded
        )
        
        data_dict = ModelSerializer.serialize_to_dict(event, exclude_none=True)
        
        assert "confirmed_at" not in data_dict
        assert "transaction_hash" in data_dict
    
    def test_deserialize_from_dict(self):
        """Test model deserialization from dictionary."""
        data_dict = {
            "transaction_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "log_index": 0,
            "block_number": 12345,
            "block_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "user_address": "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            "deposit_amount": "1000000",
            "recipient_address": "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            "nonce": 1
        }
        
        event = ModelSerializer.deserialize_from_dict(data_dict, DepositEvent)
        
        assert event.transaction_hash == data_dict["transaction_hash"]
        assert event.block_number == data_dict["block_number"]
        assert event.status == DepositStatus.PENDING  # Default value
    
    def test_deserialize_from_dict_invalid(self):
        """Test dictionary deserialization error handling."""
        invalid_dict = {"transaction_hash": "invalid"}  # Missing required fields
        
        with pytest.raises(PaymasterValidationError) as exc_info:
            ModelSerializer.deserialize_from_dict(invalid_dict, DepositEvent)
        
        assert "Failed to deserialize dict to DepositEvent" in str(exc_info.value)


class TestFileSerializer:
    """Test FileSerializer class."""
    
    def test_save_and_load_json(self):
        """Test saving and loading JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            serializer = FileSerializer(temp_dir)
            
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
            
            # Save to file
            file_path = serializer.save_json(event, "test_event.json")
            assert file_path.exists()
            
            # Load from file
            loaded_event = serializer.load_json("test_event.json", DepositEvent)
            
            assert loaded_event.transaction_hash == event.transaction_hash
            assert loaded_event.block_number == event.block_number
            assert_status_equal(loaded_event.status, event.status)
    
    def test_save_json_with_indentation(self):
        """Test JSON saving with custom indentation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            serializer = FileSerializer(temp_dir)
            
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
            
            file_path = serializer.save_json(event, "indented.json", indent=4)
            content = file_path.read_text()
            
            # Should have proper indentation
            assert "    " in content  # 4-space indentation
            assert "\n" in content
    
    def test_load_json_file_not_found(self):
        """Test loading non-existent JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            serializer = FileSerializer(temp_dir)
            
            with pytest.raises(PaymasterValidationError) as exc_info:
                serializer.load_json("nonexistent.json", DepositEvent)
            
            assert "File not found" in str(exc_info.value)
    
    def test_save_and_load_pickle(self):
        """Test saving and loading pickle files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            serializer = FileSerializer(temp_dir)
            
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
            
            # Save to pickle file
            file_path = serializer.save_pickle(event, "test_event.pkl")
            assert file_path.exists()
            
            # Load from pickle file
            loaded_event = serializer.load_pickle("test_event.pkl", DepositEvent)
            
            assert loaded_event.transaction_hash == event.transaction_hash
            assert loaded_event.block_number == event.block_number
            assert_status_equal(loaded_event.status, event.status)
    
    def test_load_pickle_wrong_type(self):
        """Test loading pickle with wrong expected type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            serializer = FileSerializer(temp_dir)
            
            # Save a DepositEvent
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
            
            serializer.save_pickle(event, "event.pkl")
            
            # Try to load as different type
            with pytest.raises(PaymasterValidationError) as exc_info:
                serializer.load_pickle("event.pkl", PriceData)
            
            assert "Expected PriceData, got DepositEvent" in str(exc_info.value)


class TestStateManager:
    """Test StateManager class."""
    
    def test_save_and_load_processing_state(self):
        """Test saving and loading processing state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_manager = StateManager(temp_dir)
            
            # Create test data
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
            
            # Save state
            file_path = state_manager.save_processing_state(state)
            assert file_path.exists()
            
            # Load state
            loaded_state = state_manager.load_processing_state(state.deposit_id)
            
            assert loaded_state is not None
            assert loaded_state.deposit_id == state.deposit_id
            assert loaded_state.deposit_event.transaction_hash == deposit_event.transaction_hash
    
    def test_load_nonexistent_processing_state(self):
        """Test loading non-existent processing state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_manager = StateManager(temp_dir)
            
            result = state_manager.load_processing_state("nonexistent:0")
            assert result is None
    
    def test_save_and_load_deposit_event(self):
        """Test saving and loading deposit events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_manager = StateManager(temp_dir)
            
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
            
            # Save event
            file_path = state_manager.save_deposit_event(event)
            assert file_path.exists()
            
            # Load event
            loaded_event = state_manager.load_deposit_event(event.get_unique_id())
            
            assert loaded_event is not None
            assert loaded_event.transaction_hash == event.transaction_hash
            assert_status_equal(loaded_event.status, event.status)
    
    def test_save_and_load_deposit_proof(self):
        """Test saving and loading deposit proofs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_manager = StateManager(temp_dir)
            
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
            
            # Save proof
            file_path = state_manager.save_deposit_proof(proof)
            assert file_path.exists()
            
            # Load proof
            loaded_proof = state_manager.load_deposit_proof(proof.deposit_id)
            
            assert loaded_proof is not None
            assert loaded_proof.deposit_id == proof.deposit_id
            assert_status_equal(loaded_proof.status, proof.status)
    
    def test_list_pending_deposits(self):
        """Test listing pending deposits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_manager = StateManager(temp_dir)
            
            # Create test deposits
            pending_event = DepositEvent(
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                log_index=0,
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="1000000",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=1,
                status=DepositStatus.PENDING
            )
            
            completed_event = DepositEvent(
                transaction_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                log_index=1,
                block_number=12346,
                block_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="2000000",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=2,
                status=DepositStatus.COMPLETED
            )
            
            # Save both events
            state_manager.save_deposit_event(pending_event)
            state_manager.save_deposit_event(completed_event)
            
            # List pending deposits
            pending_ids = state_manager.list_pending_deposits()
            
            assert len(pending_ids) == 1
            assert pending_event.get_unique_id() in pending_ids
            assert completed_event.get_unique_id() not in pending_ids
    
    def test_cleanup_old_states(self):
        """Test cleanup of old state files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_manager = StateManager(temp_dir)
            
            # Create old completed deposit
            old_event = DepositEvent(
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                log_index=0,
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="1000000",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=1,
                status=DepositStatus.COMPLETED
            )
            
            file_path = state_manager.save_deposit_event(old_event)
            
            # Manually modify file timestamp to make it old
            old_time = time.time() - 4 * 24 * 3600  # 4 days ago
            os.utime(file_path, (old_time, old_time))
            
            # Cleanup with 72 hour threshold
            cleaned_count = state_manager.cleanup_old_states(max_age_hours=72)
            
            assert cleaned_count == 1
            assert not file_path.exists()


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_serialize_model_list(self):
        """Test serializing list of models."""
        events = [
            DepositEvent(
                transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                log_index=0,
                block_number=12345,
                block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="1000000",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=1
            ),
            DepositEvent(
                transaction_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                log_index=1,
                block_number=12346,
                block_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                deposit_amount="2000000",
                recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                nonce=2
            )
        ]
        
        json_str = serialize_model_list(events)
        
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["transaction_hash"] == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        assert data[1]["transaction_hash"] == "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    
    def test_deserialize_model_list(self):
        """Test deserializing list of models."""
        json_data = '''[
            {
                "transaction_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "log_index": 0,
                "block_number": 12345,
                "block_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "user_address": "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                "deposit_amount": "1000000",
                "recipient_address": "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                "nonce": 1
            },
            {
                "transaction_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "log_index": 1,
                "block_number": 12346,
                "block_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "user_address": "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
                "deposit_amount": "2000000",
                "recipient_address": "0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
                "nonce": 2
            }
        ]'''
        
        events = deserialize_model_list(json_data, DepositEvent)
        
        assert len(events) == 2
        assert all(isinstance(event, DepositEvent) for event in events)
        assert events[0].transaction_hash == "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        assert events[1].transaction_hash == "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    
    def test_create_model_snapshot(self):
        """Test creating model snapshot."""
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
        
        metadata = {"version": "1.0", "source": "test"}
        snapshot = create_model_snapshot(event, metadata)
        
        assert "timestamp" in snapshot
        assert snapshot["model_type"] == "DepositEvent"
        assert "data" in snapshot
        assert snapshot["metadata"] == metadata
        assert isinstance(snapshot["timestamp"], float)
        assert isinstance(snapshot["data"], dict)
    
    def test_restore_model_from_snapshot(self):
        """Test restoring model from snapshot."""
        original_event = DepositEvent(
            transaction_hash="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            log_index=0,
            block_number=12345,
            block_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            user_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a800",
            deposit_amount="1000000",
            recipient_address="0x742d35Cc6634C0532925a3b8D2C2A53b69c1a801",
            nonce=1
        )
        
        snapshot = create_model_snapshot(original_event)
        restored_event = restore_model_from_snapshot(snapshot, DepositEvent)
        
        assert restored_event.transaction_hash == original_event.transaction_hash
        assert restored_event.block_number == original_event.block_number
        assert_status_equal(restored_event.status, original_event.status)
    
    def test_restore_model_type_mismatch(self):
        """Test restoring model with wrong type."""
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
        
        snapshot = create_model_snapshot(event)
        
        with pytest.raises(PaymasterValidationError) as exc_info:
            restore_model_from_snapshot(snapshot, PriceData)
        
        assert "Model type mismatch" in str(exc_info.value)
        assert "expected PriceData, got DepositEvent" in str(exc_info.value)