"""
Shared data models for ROFL Relayer.

This module contains data classes and types used across the relayer components.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PingEvent:
    """Represents a Ping event from the source chain.
    
    Using frozen=True for immutability and slots=True for memory efficiency
    (Python 3.10+ feature for better performance).
    
    Attributes:
        tx_hash: Transaction hash where the event was emitted
        block_number: Block number where the event occurred
        sender: Address that sent the ping
        timestamp: Unix timestamp of the ping
        ping_id: Unique identifier for this ping event
    """
    tx_hash: str
    block_number: int
    sender: str
    timestamp: int
    ping_id: str