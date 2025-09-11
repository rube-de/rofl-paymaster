"""
Event processor for handling blockchain events.

This module contains the logic for processing Ping and HashStored events,
keeping the processing logic separate from the relay orchestration.
"""

import contextlib
import logging
from collections import OrderedDict, deque
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional

from web3 import Web3
from web3.types import EventData

from .models import PingEvent
from .proof_manager import ProofManager

if TYPE_CHECKING:
    from .config import RelayerConfig

logger = logging.getLogger(__name__)


class EventProcessor:
    """Processes blockchain events for the ROFL relayer."""

    MAX_PROCESSED_HASHES: int = 10_000
    MAX_PENDING_PINGS: int = 10_000
    MAX_STORED_HASHES: int = 10_000  # Prevent memory leak

    def __init__(
        self,
        proof_manager: ProofManager | None = None,
        config: Optional["RelayerConfig"] = None,
    ) -> None:
        """Initialize the event processor.

        Args:
            proof_manager: ProofManager instance for generating and submitting proofs
            config: RelayerConfig instance for accessing target addresses
        """
        # State tracking with bounded collections
        # OrderedDict provides O(1) lookups and maintains insertion order for LRU
        self.processed_tx_hashes: OrderedDict[str, None] = OrderedDict()

        # Primary structure: dict for O(1) lookup by block_number
        self.pending_pings: dict[int, list[PingEvent]] = {}
        # Secondary structure: deque for O(1) FIFO removal of oldest pings
        self.pending_pings_order: deque[PingEvent] = deque()

        # Use OrderedDict with size limit to prevent memory leak
        self.stored_hashes: OrderedDict[int, str] = OrderedDict()

        # Proof generation
        self.proof_manager = proof_manager
        self.config = config

    async def process_ping_event(self, event: EventData) -> PingEvent | None:
        """
        Process a Ping event from the source chain.

        Args:
            event: The Ping event data

        Returns:
            PingEvent if successfully processed, None if skipped or error
        """
        try:
            match event.get("transactionHash"):
                case None:
                    logger.warning("Event missing transaction hash")
                    return None
                case bytes() as tx_hash_bytes:
                    tx_hash = tx_hash_bytes.hex()
                case str() as tx_hash:
                    pass  # Already a string
                case _:
                    logger.warning(
                        f"Unexpected transaction hash type: {type(event.get('transactionHash'))}"
                    )
                    return None

            # Skip if already processed
            if tx_hash in self.processed_tx_hashes:
                return None

            # Track processed transaction
            self._track_processed_hash(tx_hash)

            # Extract event data with type safety
            block_number: int = event.get("blockNumber", 0)
            args: Mapping[str, Any] = event.get("args", {})
            sender: str = args.get("sender", "0x0")
            timestamp: int = args.get("timestamp", 0)

            # Generate ping ID using transaction hash and event args for uniqueness
            ping_id: str = Web3.keccak(text=f"{tx_hash}-{sender}-{block_number}").hex()

            # Create typed ping event
            ping_event = PingEvent(
                tx_hash=tx_hash,
                block_number=block_number,
                sender=sender,
                timestamp=timestamp,
                ping_id=ping_id,
            )

            logger.info(
                f"Ping event detected - TX: {tx_hash[:10]}... {block_number=} "
                f"{sender=} ID: {ping_id[:10]}..."
            )

            # Check capacity and remove oldest if needed
            if len(self.pending_pings_order) >= self.MAX_PENDING_PINGS:
                oldest_ping = self.pending_pings_order.popleft()

                if oldest_ping.block_number in self.pending_pings:
                    block_pings = self.pending_pings[oldest_ping.block_number]
                    if oldest_ping in block_pings:
                        block_pings.remove(oldest_ping)
                        if not block_pings:
                            del self.pending_pings[oldest_ping.block_number]

                logger.debug(
                    f"Removed oldest ping {oldest_ping.ping_id[:10]}... due to capacity"
                )

            # Add to both structures
            if block_number not in self.pending_pings:
                self.pending_pings[block_number] = []
            self.pending_pings[block_number].append(ping_event)

            self.pending_pings_order.append(ping_event)

            return ping_event

        except Exception as e:
            logger.error(f"Error processing ping event: {e}", exc_info=True)
            return None

    async def process_hash_stored(self, event: EventData) -> tuple[int, str] | None:
        """
        Process a HashStored event from the ROFLAdapter.

        Args:
            event: The HashStored event data

        Returns:
            Tuple of (block_id, block_hash) if successful, None if error
        """
        try:
            # Extract event data with pattern matching
            args: Mapping[str, Any] = event.get("args", {})
            block_id: int = args.get("id", 0)

            # Handle block hash with pattern matching
            match args.get("hash", "0x0"):
                case bytes() as hash_bytes:
                    block_hash = hash_bytes.hex()
                case str() as hash_str:
                    block_hash = hash_str
                case _:
                    block_hash = "0x0"

            # Store the hash with automatic eviction to prevent memory leak
            if len(self.stored_hashes) >= self.MAX_STORED_HASHES:
                self.stored_hashes.popitem(last=False)

            self.stored_hashes[block_id] = block_hash

            logger.info(f"Hash stored - Block {block_id}: {block_hash[:10]}...")

            matching_pings: list[PingEvent] = self.pending_pings.get(block_id, [])
            if matching_pings:
                logger.info(
                    f"Found {len(matching_pings)} pings ready for block {block_id}"
                )
                # Process matched events with proof generation
                if self.proof_manager and self.config:
                    for ping in matching_pings:
                        await self.process_matched_events(ping)

            return (block_id, block_hash)

        except Exception as e:
            logger.error(f"Error processing HashStored event: {e}", exc_info=True)
            return None

    def _track_processed_hash(self, tx_hash: str) -> None:
        """
        Track a processed transaction hash with automatic LRU eviction.

        Uses OrderedDict for O(1) lookups and automatic LRU behavior.
        When we reach capacity, we remove the oldest entry (first inserted).

        Args:
            tx_hash: Transaction hash to track
        """
        if tx_hash in self.processed_tx_hashes:
            self.processed_tx_hashes.move_to_end(tx_hash)
        else:
            if len(self.processed_tx_hashes) >= self.MAX_PROCESSED_HASHES:
                self.processed_tx_hashes.popitem(last=False)

            self.processed_tx_hashes[tx_hash] = None

    async def process_matched_events(self, ping_event: PingEvent) -> None:
        """
        Process matched Ping and HashStored events by generating and submitting proof.

        Args:
            ping_event: The Ping event to process
        """
        try:
            if not self.proof_manager or not self.config:
                logger.warning(
                    "ProofManager or config not initialized, skipping proof generation"
                )
                return

            receiver_address = self.config.target_chain.ping_receiver_address
            logger.info(
                f"Processing proof for Ping {ping_event.ping_id[:10]}... to receiver {receiver_address}"
            )

            # Generate and submit proof
            tx_hash = await self.proof_manager.process_ping_event(
                ping_event, receiver_address
            )

            logger.info(f"Proof submitted successfully: {tx_hash}")

            block_pings = self.pending_pings.get(ping_event.block_number, [])
            if ping_event in block_pings:
                block_pings.remove(ping_event)
                if not block_pings:
                    del self.pending_pings[ping_event.block_number]

            with contextlib.suppress(ValueError):
                self.pending_pings_order.remove(ping_event)

        except Exception as e:
            logger.error(
                f"Failed to process proof for Ping {ping_event.ping_id[:10]}...: {e}",
                exc_info=True,
            )

    def get_stats(self) -> dict:
        """
        Get current processor statistics.

        Returns:
            Dictionary with current state metrics
        """
        return {
            "processed_hashes": len(self.processed_tx_hashes),
            "pending_pings": len(self.pending_pings_order),
            "stored_hashes": len(self.stored_hashes),
        }
