"""
ROFL Relayer implementation.

This module contains the main relayer service that orchestrates event monitoring
and coordinates with the event processor for handling blockchain events.
"""

import asyncio
import logging
from typing import Optional

from web3.types import EventData

from web3 import Web3

from .config import RelayerConfig
from .event_processor import EventProcessor
from .proof_manager import ProofManager
from .utils.polling_event_listener import PollingEventListener
from .utils.contract_utility import ContractUtility
from .utils.rofl_utility import RoflUtility

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ROFLRelayer:
    """
    Main relayer service that orchestrates event monitoring and processing.
    
    This class focuses on coordination and lifecycle management, delegating
    event processing logic to the EventProcessor.
    """
    
    STATUS_LOG_INTERVAL = 30  # seconds

    def __init__(self, config: RelayerConfig):
        """
        Initialize the ROFL Relayer.

        Args:
            config: Relayer configuration
        """
        self.config = config
        self.running = False
        
        self._init_utilities()
        
        self.event_processor = EventProcessor(
            proof_manager=self.proof_manager,
            config=config
        )
        self.ping_listener: Optional[PollingEventListener] = None
        self.hash_listener: Optional[PollingEventListener] = None
        
        self.shutdown_event = asyncio.Event()
    
    def _init_utilities(self) -> None:
        """
        Initialize utility classes for proof generation.
        """
        # Initialize Web3 for source chain
        self.w3_source = Web3(Web3.HTTPProvider(self.config.source_chain.rpc_url))
        if not self.w3_source.is_connected():
            raise Exception(f"Failed to connect to source chain at {self.config.source_chain.rpc_url}")
        
        # Initialize contract utility for target chain
        self.contract_util = ContractUtility(
            rpc_url=self.config.target_chain.rpc_url,
            secret=self.config.target_chain.private_key or ""
        )
        
        self.rofl_util = None if self.config.local_mode else RoflUtility()
        
        self.proof_manager = ProofManager(
            w3_source=self.w3_source,
            contract_util=self.contract_util,
            rofl_util=self.rofl_util
        )
        
        source_chain_id = self.w3_source.eth.chain_id
        logger.info(f"ROFL Relayer initialized ({'LOCAL' if self.config.local_mode else 'ROFL'} mode, source chain: {source_chain_id})")
    
    @classmethod
    def from_env(cls, local_mode: bool = False) -> "ROFLRelayer":
        """
        Create a ROFLRelayer instance from environment variables.
        
        Args:
            local_mode: Run in local mode without ROFL utilities
            
        Returns:
            Configured ROFLRelayer instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        config = RelayerConfig.from_env(local_mode=local_mode)
        config.log_config()
        return cls(config)
    
    async def init_event_monitoring(self) -> None:
        """Initialize polling listeners for both chains."""
        logger.info("Initializing event monitoring...")
        
        # Load ABIs
        ping_sender_abi = self.contract_util.get_contract_abi("PingSender")
        rofl_adapter_abi = self.contract_util.get_contract_abi("ROFLAdapter")
        
        # Initialize PingSender event listener (source chain)
        self.ping_listener = PollingEventListener(
            rpc_url=self.config.source_chain.rpc_url,
            contract_address=self.config.source_chain.ping_sender_address,
            event_name="Ping",
            abi=ping_sender_abi,
            lookback_blocks=self.config.monitoring.lookback_blocks
        )
        
        # Initialize ROFLAdapter event listener (target chain - Sapphire)
        self.hash_listener = PollingEventListener(
            rpc_url=self.config.target_chain.rpc_url,
            contract_address=self.config.target_chain.rofl_adapter_address,
            event_name="HashStored", 
            abi=rofl_adapter_abi,
            lookback_blocks=self.config.monitoring.lookback_blocks
        )
        
        logger.info(f"PingSender listener: {self.config.source_chain.ping_sender_address}")
        logger.info(f"ROFLAdapter listener: {self.config.target_chain.rofl_adapter_address}")
    
    
    async def _periodic_status_logger(self) -> None:
        """Log status periodically while running."""
        while self.running:
            await asyncio.sleep(self.STATUS_LOG_INTERVAL)
            stats = self.event_processor.get_stats()
            if stats['pending_pings'] > 0:
                logger.info(
                    f"Status: {stats['pending_pings']} pings pending, "
                    f"{stats['processed_hashes']} processed, "
                    f"{stats['stored_hashes']} hashes stored"
                )
    
    async def _check_task_health(self, tasks: dict[str, asyncio.Task]) -> bool:
        """Check if any critical task has failed."""
        for name, task in tasks.items():
            if task.done() and name != "status":
                try:
                    await task
                except Exception as e:
                    logger.error(f"{name} task failed: {e}", exc_info=True)
                return False
        return True
    
    async def _cleanup_tasks(self, tasks: dict[str, asyncio.Task]) -> None:
        """Clean up all tasks and listeners."""
        # Stop polling listeners
        if self.ping_listener:
            await self.ping_listener.stop()
        if self.hash_listener:
            await self.hash_listener.stop()
        
        # Cancel all running tasks
        for name, task in tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    async def run(self) -> None:
        """Main event loop for the relayer service."""
        self.running = True
        logger.info("ROFL Relayer starting...")
        logger.info(f"Polling interval: {self.config.monitoring.polling_interval}s")
        logger.info(f"Lookback blocks: {self.config.monitoring.lookback_blocks}")
        
        tasks = {}
        try:
            await self.init_event_monitoring()
            
            # Ensure listeners are initialized
            if not self.ping_listener or not self.hash_listener:
                raise RuntimeError("Event listeners not properly initialized")
            
            tasks = {
                "ping": asyncio.create_task(
                    self.ping_listener.start_polling(
                        callback=self.event_processor.process_ping_event,
                        interval=self.config.monitoring.polling_interval
                    )
                ),
                "hash": asyncio.create_task(
                    self.hash_listener.start_polling(
                        callback=self.event_processor.process_hash_stored,
                        interval=self.config.monitoring.polling_interval
                    )
                ),
                "status": asyncio.create_task(self._periodic_status_logger())
            }
            
            logger.info("Event monitoring started, waiting for events...")
            
            # Wait until shutdown or task failure
            while self.running:
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=1.0)
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    pass  # Continue running
                
                # Check task health
                if not await self._check_task_health(tasks):
                    logger.error("Critical task failure, shutting down")
                    break
        
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            raise
        finally:
            await self._cleanup_tasks(tasks)
            logger.info("ROFL Relayer stopped")

    def stop(self) -> None:
        """Stop the relayer service."""
        self.running = False
        self.shutdown_event.set()