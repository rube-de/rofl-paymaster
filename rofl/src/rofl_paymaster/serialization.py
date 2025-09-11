"""Serialization and deserialization utilities for paymaster models."""

import json
import pickle
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .models import (
    DepositEvent, DepositProof, PriceData, ProcessingState,
    DepositStatus, ProofStatus, TransactionStatus
)
from .exceptions import ValidationError as PaymasterValidationError
from .logging import get_logger

T = TypeVar('T', bound=BaseModel)

logger = get_logger("serialization")


class ModelSerializer:
    """Handles serialization and deserialization of Pydantic models."""
    
    @staticmethod
    def serialize_to_json(model: BaseModel, indent: Optional[int] = None, ensure_ascii: bool = False) -> str:
        """Serialize model to JSON string.
        
        Args:
            model: Pydantic model to serialize
            indent: JSON indentation (None for compact)
            ensure_ascii: Whether to escape non-ASCII characters
            
        Returns:
            JSON string representation
            
        Raises:
            PaymasterValidationError: If serialization fails
        """
        try:
            return model.model_dump_json(indent=indent, by_alias=True)
        except Exception as e:
            raise PaymasterValidationError(
                f"Failed to serialize {model.__class__.__name__} to JSON: {e}",
                field="serialization",
                value=str(model),
                details={"model_type": model.__class__.__name__, "error": str(e)}
            )
    
    @staticmethod
    def deserialize_from_json(json_str: str, model_class: Type[T]) -> T:
        """Deserialize model from JSON string.
        
        Args:
            json_str: JSON string to deserialize
            model_class: Pydantic model class
            
        Returns:
            Deserialized model instance
            
        Raises:
            PaymasterValidationError: If deserialization fails
        """
        try:
            # Parse JSON and validate - field validators will handle enum conversion
            data = json.loads(json_str)
            return model_class.model_validate(data)
        except ValidationError as e:
            raise PaymasterValidationError(
                f"Failed to deserialize JSON to {model_class.__name__}: {e}",
                field="deserialization",
                value=json_str[:200] + "..." if len(json_str) > 200 else json_str,
                details={"model_type": model_class.__name__, "validation_errors": e.errors()}
            )
        except Exception as e:
            raise PaymasterValidationError(
                f"Failed to deserialize JSON to {model_class.__name__}: {e}",
                field="deserialization",
                value=json_str[:200] + "..." if len(json_str) > 200 else json_str,
                details={"model_type": model_class.__name__, "error": str(e)}
            )
    
    @staticmethod
    def serialize_to_dict(model: BaseModel, by_alias: bool = False, exclude_none: bool = False) -> Dict[str, Any]:
        """Serialize model to dictionary.
        
        Args:
            model: Pydantic model to serialize
            by_alias: Use field aliases in output
            exclude_none: Exclude None values
            
        Returns:
            Dictionary representation
            
        Raises:
            PaymasterValidationError: If serialization fails
        """
        try:
            return model.model_dump(by_alias=by_alias, exclude_none=exclude_none, mode='json')
        except Exception as e:
            raise PaymasterValidationError(
                f"Failed to serialize {model.__class__.__name__} to dict: {e}",
                field="serialization",
                value=str(model),
                details={"model_type": model.__class__.__name__, "error": str(e)}
            )
    
    @staticmethod
    def deserialize_from_dict(data: Dict[str, Any], model_class: Type[T]) -> T:
        """Deserialize model from dictionary.
        
        Args:
            data: Dictionary data to deserialize
            model_class: Pydantic model class
            
        Returns:
            Deserialized model instance
            
        Raises:
            PaymasterValidationError: If deserialization fails
        """
        try:
            return model_class.model_validate(data)
        except ValidationError as e:
            raise PaymasterValidationError(
                f"Failed to deserialize dict to {model_class.__name__}: {e}",
                field="deserialization",
                value=str(data)[:200] + "..." if len(str(data)) > 200 else str(data),
                details={"model_type": model_class.__name__, "validation_errors": e.errors()}
            )
        except Exception as e:
            raise PaymasterValidationError(
                f"Failed to deserialize dict to {model_class.__name__}: {e}",
                field="deserialization",
                value=str(data)[:200] + "..." if len(str(data)) > 200 else str(data),
                details={"model_type": model_class.__name__, "error": str(e)}
            )


class FileSerializer:
    """Handles file-based serialization and deserialization."""
    
    def __init__(self, base_path: Optional[str] = None):
        """Initialize file serializer.
        
        Args:
            base_path: Base directory for file operations
        """
        self.base_path = Path(base_path) if base_path else Path(".")
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_json(self, model: BaseModel, filename: str, indent: int = 2) -> Path:
        """Save model to JSON file.
        
        Args:
            model: Model to save
            filename: Output filename
            indent: JSON indentation
            
        Returns:
            Path to saved file
            
        Raises:
            PaymasterValidationError: If save fails
        """
        try:
            file_path = self.base_path / filename
            json_str = ModelSerializer.serialize_to_json(model, indent=indent)
            
            file_path.write_text(json_str, encoding='utf-8')
            logger.debug(f"Saved {model.__class__.__name__} to {file_path}")
            
            return file_path
            
        except Exception as e:
            raise PaymasterValidationError(
                f"Failed to save {model.__class__.__name__} to {filename}: {e}",
                field="file_save",
                value=filename,
                details={"model_type": model.__class__.__name__, "error": str(e)}
            )
    
    def load_json(self, filename: str, model_class: Type[T]) -> T:
        """Load model from JSON file.
        
        Args:
            filename: Input filename
            model_class: Model class to deserialize to
            
        Returns:
            Loaded model instance
            
        Raises:
            PaymasterValidationError: If load fails
        """
        try:
            file_path = self.base_path / filename
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            json_str = file_path.read_text(encoding='utf-8')
            model = ModelSerializer.deserialize_from_json(json_str, model_class)
            
            logger.debug(f"Loaded {model_class.__name__} from {file_path}")
            return model
            
        except Exception as e:
            raise PaymasterValidationError(
                f"Failed to load {model_class.__name__} from {filename}: {e}",
                field="file_load",
                value=filename,
                details={"model_type": model_class.__name__, "error": str(e)}
            )
    
    def save_pickle(self, model: BaseModel, filename: str) -> Path:
        """Save model to pickle file.
        
        Args:
            model: Model to save
            filename: Output filename
            
        Returns:
            Path to saved file
            
        Raises:
            PaymasterValidationError: If save fails
        """
        try:
            file_path = self.base_path / filename
            
            with file_path.open('wb') as f:
                pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            logger.debug(f"Saved {model.__class__.__name__} to {file_path} (pickle)")
            return file_path
            
        except Exception as e:
            raise PaymasterValidationError(
                f"Failed to save {model.__class__.__name__} to {filename} (pickle): {e}",
                field="pickle_save",
                value=filename,
                details={"model_type": model.__class__.__name__, "error": str(e)}
            )
    
    def load_pickle(self, filename: str, model_class: Type[T]) -> T:
        """Load model from pickle file.
        
        Args:
            filename: Input filename
            model_class: Expected model class (for type checking)
            
        Returns:
            Loaded model instance
            
        Raises:
            PaymasterValidationError: If load fails
        """
        try:
            file_path = self.base_path / filename
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with file_path.open('rb') as f:
                model = pickle.load(f)
            
            # Validate that loaded object is of expected type
            if not isinstance(model, model_class):
                raise TypeError(f"Expected {model_class.__name__}, got {type(model).__name__}")
            
            logger.debug(f"Loaded {model_class.__name__} from {file_path} (pickle)")
            return model
            
        except Exception as e:
            raise PaymasterValidationError(
                f"Failed to load {model_class.__name__} from {filename} (pickle): {e}",
                field="pickle_load",
                value=filename,
                details={"model_type": model_class.__name__, "error": str(e)}
            )


class StateManager:
    """Manager for persistent state storage and retrieval."""
    
    def __init__(self, state_dir: Optional[str] = None):
        """Initialize state manager.
        
        Args:
            state_dir: Directory for state files
        """
        self.state_dir = Path(state_dir) if state_dir else Path("./state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.file_serializer = FileSerializer(str(self.state_dir))
    
    def save_processing_state(self, state: ProcessingState) -> Path:
        """Save processing state to file.
        
        Args:
            state: Processing state to save
            
        Returns:
            Path to saved file
        """
        filename = f"processing_state_{state.deposit_id.replace(':', '_')}.json"
        return self.file_serializer.save_json(state, filename)
    
    def load_processing_state(self, deposit_id: str) -> Optional[ProcessingState]:
        """Load processing state from file.
        
        Args:
            deposit_id: Deposit ID to load state for
            
        Returns:
            Processing state if found, None otherwise
        """
        filename = f"processing_state_{deposit_id.replace(':', '_')}.json"
        
        try:
            return self.file_serializer.load_json(filename, ProcessingState)
        except PaymasterValidationError as e:
            if "File not found" in str(e):
                return None
            raise
    
    def save_deposit_event(self, deposit: DepositEvent) -> Path:
        """Save deposit event to file.
        
        Args:
            deposit: Deposit event to save
            
        Returns:
            Path to saved file
        """
        filename = f"deposit_{deposit.get_unique_id().replace(':', '_')}.json"
        return self.file_serializer.save_json(deposit, filename)
    
    def load_deposit_event(self, deposit_id: str) -> Optional[DepositEvent]:
        """Load deposit event from file.
        
        Args:
            deposit_id: Deposit ID to load
            
        Returns:
            Deposit event if found, None otherwise
        """
        filename = f"deposit_{deposit_id.replace(':', '_')}.json"
        
        try:
            return self.file_serializer.load_json(filename, DepositEvent)
        except PaymasterValidationError as e:
            if "File not found" in str(e):
                return None
            raise
    
    def save_deposit_proof(self, proof: DepositProof) -> Path:
        """Save deposit proof to file.
        
        Args:
            proof: Deposit proof to save
            
        Returns:
            Path to saved file
        """
        filename = f"proof_{proof.deposit_id.replace(':', '_')}.json"
        return self.file_serializer.save_json(proof, filename)
    
    def load_deposit_proof(self, deposit_id: str) -> Optional[DepositProof]:
        """Load deposit proof from file.
        
        Args:
            deposit_id: Deposit ID to load proof for
            
        Returns:
            Deposit proof if found, None otherwise
        """
        filename = f"proof_{deposit_id.replace(':', '_')}.json"
        
        try:
            return self.file_serializer.load_json(filename, DepositProof)
        except PaymasterValidationError as e:
            if "File not found" in str(e):
                return None
            raise
    
    def list_pending_deposits(self) -> List[str]:
        """List all pending deposit IDs.
        
        Returns:
            List of deposit IDs with pending status
        """
        pending_deposits = []
        
        for file_path in self.state_dir.glob("deposit_*.json"):
            try:
                deposit = self.file_serializer.load_json(file_path.name, DepositEvent)
                if deposit.status == DepositStatus.PENDING:
                    pending_deposits.append(deposit.get_unique_id())
            except Exception as e:
                logger.warning(f"Failed to load deposit from {file_path}: {e}")
        
        return pending_deposits
    
    def list_processing_states(self) -> List[str]:
        """List all processing state deposit IDs.
        
        Returns:
            List of deposit IDs with processing states
        """
        processing_deposits = []
        
        for file_path in self.state_dir.glob("processing_state_*.json"):
            try:
                state = self.file_serializer.load_json(file_path.name, ProcessingState)
                processing_deposits.append(state.deposit_id)
            except Exception as e:
                logger.warning(f"Failed to load processing state from {file_path}: {e}")
        
        return processing_deposits
    
    def cleanup_old_states(self, max_age_hours: int = 72) -> int:
        """Clean up old state files.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            Number of files cleaned up
        """
        cleaned_count = 0
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for file_path in self.state_dir.glob("*.json"):
            try:
                if file_path.stat().st_mtime < cutoff_time:
                    # Check if it's a completed or failed state
                    if file_path.name.startswith("processing_state_"):
                        state = self.file_serializer.load_json(file_path.name, ProcessingState)
                        if state.is_complete() or state.is_failed():
                            file_path.unlink()
                            cleaned_count += 1
                    elif file_path.name.startswith("deposit_"):
                        deposit = self.file_serializer.load_json(file_path.name, DepositEvent)
                        if deposit.status in (DepositStatus.COMPLETED, DepositStatus.FAILED, DepositStatus.EXPIRED):
                            file_path.unlink()
                            cleaned_count += 1
                        
            except Exception as e:
                logger.warning(f"Failed to process file {file_path} during cleanup: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old state files")
        
        return cleaned_count


# Utility functions for common serialization patterns

def serialize_model_list(models: List[BaseModel], indent: Optional[int] = None) -> str:
    """Serialize list of models to JSON.
    
    Args:
        models: List of models to serialize
        indent: JSON indentation
        
    Returns:
        JSON string representation
    """
    data = [ModelSerializer.serialize_to_dict(model) for model in models]
    return json.dumps(data, indent=indent, default=str)


def deserialize_model_list(json_str: str, model_class: Type[T]) -> List[T]:
    """Deserialize list of models from JSON.
    
    Args:
        json_str: JSON string containing list of models
        model_class: Model class to deserialize to
        
    Returns:
        List of deserialized models
    """
    try:
        data_list = json.loads(json_str)
        return [ModelSerializer.deserialize_from_dict(data, model_class) for data in data_list]
    except Exception as e:
        raise PaymasterValidationError(
            f"Failed to deserialize model list: {e}",
            field="list_deserialization",
            details={"model_type": model_class.__name__, "error": str(e)}
        )


def create_model_snapshot(model: BaseModel, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a snapshot of a model with metadata.
    
    Args:
        model: Model to snapshot
        metadata: Additional metadata to include
        
    Returns:
        Snapshot dictionary
    """
    snapshot = {
        "timestamp": time.time(),
        "model_type": model.__class__.__name__,
        "data": ModelSerializer.serialize_to_dict(model),
    }
    
    if metadata:
        snapshot["metadata"] = metadata
    
    return snapshot


def restore_model_from_snapshot(snapshot: Dict[str, Any], model_class: Type[T]) -> T:
    """Restore model from snapshot.
    
    Args:
        snapshot: Snapshot dictionary
        model_class: Expected model class
        
    Returns:
        Restored model instance
    """
    if snapshot.get("model_type") != model_class.__name__:
        raise PaymasterValidationError(
            f"Model type mismatch: expected {model_class.__name__}, got {snapshot.get('model_type')}",
            field="snapshot_restore"
        )
    
    return ModelSerializer.deserialize_from_dict(snapshot["data"], model_class)