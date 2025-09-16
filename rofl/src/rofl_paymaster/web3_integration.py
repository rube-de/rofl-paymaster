"""Comprehensive Web3 integration layer combining all connection management components."""

import asyncio
from typing import Dict, Optional, Any, Callable, List
from contextlib import asynccontextmanager

from web3 import Web3, AsyncWeb3
from web3.types import LogReceipt, FilterParams

from .config import Web3Config, MonitoringConfig
from .connection import ConnectionManager
from .connection_pool import ConnectionPool
from .websocket_manager import WebSocketManager
from .web3_helpers import Web3Helpers
from .logging import get_logger


class Web3Integration:
    """Comprehensive Web3 integration layer for ROFL Paymaster.
    
    This class provides a unified interface for all Web3 operations, combining:
    - Connection management with failover
    - Connection pooling for performance
    - WebSocket event monitoring
    - Utility functions for blockchain operations
    """
    
    def __init__(
        self,
        base_chain_config: Web3Config,
        sapphire_chain_config: Web3Config,
        monitoring_config: MonitoringConfig,
        enable_connection_pool: bool = True,
        pool_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize Web3 integration layer.
        
        Args:
            base_chain_config: Base L2 chain configuration
            sapphire_chain_config: Oasis Sapphire chain configuration
            monitoring_config: Event monitoring configuration
            enable_connection_pool: Enable connection pooling
            pool_config: Connection pool configuration overrides
        """
        self.base_config = base_chain_config
        self.sapphire_config = sapphire_chain_config
        self.monitoring_config = monitoring_config
        self.enable_connection_pool = enable_connection_pool
        self.logger = get_logger("web3_integration")
        
        # Connection managers
        self.base_connection_manager: Optional[ConnectionManager] = None
        self.sapphire_connection_manager: Optional[ConnectionManager] = None
        
        # Connection pools (optional)
        self.base_connection_pool: Optional[ConnectionPool] = None
        self.sapphire_connection_pool: Optional[ConnectionPool] = None
        
        # WebSocket managers
        self.base_websocket_manager: Optional[WebSocketManager] = None
        self.sapphire_websocket_manager: Optional[WebSocketManager] = None
        
        # Web3 helpers
        self.base_helpers: Optional[Web3Helpers] = None
        self.sapphire_helpers: Optional[Web3Helpers] = None
        
        # Pool configuration
        default_pool_config = {
            "min_connections": 2,
            "max_connections": 10,
            "max_connection_age": 3600.0,
            "max_idle_time": 300.0,
            "connection_timeout": 30.0,
        }
        if pool_config:
            default_pool_config.update(pool_config)
        self.pool_config = default_pool_config
    
    async def initialize(self) -> None:
        """Initialize all Web3 components."""
        self.logger.info("Initializing Web3 integration layer")
        
        try:
            # Initialize Base chain components
            await self._initialize_base_chain()
            
            # Initialize Sapphire chain components  
            await self._initialize_sapphire_chain()
            
            self.logger.info("Web3 integration layer initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Web3 integration layer: {e}")
            await self.shutdown()
            raise
    
    async def _initialize_base_chain(self) -> None:
        """Initialize Base chain components."""
        self.logger.info("Initializing Base chain components")
        
        # Connection manager
        self.base_connection_manager = ConnectionManager(
            config=self.base_config,
            chain_name="base"
        )
        await self.base_connection_manager.initialize()
        
        # Connection pool (optional)
        if self.enable_connection_pool:
            self.base_connection_pool = ConnectionPool(
                config=self.base_config,
                chain_name="base",
                **self.pool_config
            )
            await self.base_connection_pool.initialize()
        
        # WebSocket manager (if WebSocket URLs provided)
        if self.base_config.websocket_urls:
            self.base_websocket_manager = WebSocketManager(
                config=self.base_config,
                monitoring_config=self.monitoring_config,
                chain_name="base"
            )
            await self.base_websocket_manager.initialize()
        
        # Web3 helpers
        if self.base_connection_manager.web3 and self.base_connection_manager.async_web3:
            self.base_helpers = Web3Helpers(
                web3=self.base_connection_manager.web3,
                async_web3=self.base_connection_manager.async_web3,
                config=self.base_config
            )
        
        self.logger.info("Base chain components initialized")
    
    async def _initialize_sapphire_chain(self) -> None:
        """Initialize Sapphire chain components."""
        self.logger.info("Initializing Sapphire chain components")
        
        # Connection manager
        self.sapphire_connection_manager = ConnectionManager(
            config=self.sapphire_config,
            chain_name="sapphire"
        )
        await self.sapphire_connection_manager.initialize()
        
        # Connection pool (optional)
        if self.enable_connection_pool:
            self.sapphire_connection_pool = ConnectionPool(
                config=self.sapphire_config,
                chain_name="sapphire",
                **self.pool_config
            )
            await self.sapphire_connection_pool.initialize()
        
        # WebSocket manager (if WebSocket URLs provided)
        if self.sapphire_config.websocket_urls:
            self.sapphire_websocket_manager = WebSocketManager(
                config=self.sapphire_config,
                monitoring_config=self.monitoring_config,
                chain_name="sapphire"
            )
            await self.sapphire_websocket_manager.initialize()
        
        # Web3 helpers
        if self.sapphire_connection_manager.web3 and self.sapphire_connection_manager.async_web3:
            self.sapphire_helpers = Web3Helpers(
                web3=self.sapphire_connection_manager.web3,
                async_web3=self.sapphire_connection_manager.async_web3,
                config=self.sapphire_config
            )
        
        self.logger.info("Sapphire chain components initialized")
    
    async def shutdown(self) -> None:
        """Shutdown all Web3 components."""
        self.logger.info("Shutting down Web3 integration layer")
        
        # Shutdown Base chain components
        if self.base_websocket_manager:
            await self.base_websocket_manager.shutdown()
        if self.base_connection_pool:
            await self.base_connection_pool.shutdown()
        if self.base_connection_manager:
            await self.base_connection_manager.shutdown()
        
        # Shutdown Sapphire chain components  
        if self.sapphire_websocket_manager:
            await self.sapphire_websocket_manager.shutdown()
        if self.sapphire_connection_pool:
            await self.sapphire_connection_pool.shutdown()
        if self.sapphire_connection_manager:
            await self.sapphire_connection_manager.shutdown()
        
        self.logger.info("Web3 integration layer shut down")
    
    # Base Chain Access Methods
    
    @asynccontextmanager
    async def get_base_connection(self, prefer_websocket: bool = False, use_pool: bool = None):
        """Get Base chain connection with automatic failover.
        
        Args:
            prefer_websocket: Prefer WebSocket connection if available
            use_pool: Use connection pool if available (defaults to pool enablement)
            
        Yields:
            Web3 instance for Base chain
        """
        use_pool = use_pool if use_pool is not None else self.enable_connection_pool
        
        if use_pool and self.base_connection_pool:
            async with self.base_connection_pool.get_connection() as pooled_connection:
                yield pooled_connection.web3
        elif self.base_connection_manager:
            async with self.base_connection_manager.get_connection(prefer_websocket) as web3:
                yield web3
        else:
            raise ConnectionError("No Base chain connection available")
    
    @asynccontextmanager
    async def get_sapphire_connection(self, prefer_websocket: bool = False, use_pool: bool = None):
        """Get Sapphire chain connection with automatic failover.
        
        Args:
            prefer_websocket: Prefer WebSocket connection if available  
            use_pool: Use connection pool if available (defaults to pool enablement)
            
        Yields:
            Web3 instance for Sapphire chain
        """
        use_pool = use_pool if use_pool is not None else self.enable_connection_pool
        
        if use_pool and self.sapphire_connection_pool:
            async with self.sapphire_connection_pool.get_connection() as pooled_connection:
                yield pooled_connection.web3
        elif self.sapphire_connection_manager:
            async with self.sapphire_connection_manager.get_connection(prefer_websocket) as web3:
                yield web3
        else:
            raise ConnectionError("No Sapphire chain connection available")
    
    # Event Monitoring Methods
    
    async def subscribe_to_base_events(
        self,  
        contract_address: str,
        event_signature: str,
        callback: Callable[[LogReceipt], None],
        filter_params: Optional[FilterParams] = None
    ) -> str:
        """Subscribe to Base chain events.
        
        Args:
            contract_address: Contract address to monitor
            event_signature: Event signature hash
            callback: Callback function for events
            filter_params: Optional filter parameters
            
        Returns:
            Subscription ID
            
        Raises:
            ConnectionError: If WebSocket not available
        """
        if not self.base_websocket_manager:
            raise ConnectionError("Base WebSocket manager not available")
        
        return await self.base_websocket_manager.subscribe_to_events(
            contract_address=contract_address,
            event_signature=event_signature,
            callback=callback,
            filter_params=filter_params
        )
    
    async def subscribe_to_sapphire_events(
        self,
        contract_address: str, 
        event_signature: str,
        callback: Callable[[LogReceipt], None],
        filter_params: Optional[FilterParams] = None
    ) -> str:
        """Subscribe to Sapphire chain events.
        
        Args:
            contract_address: Contract address to monitor
            event_signature: Event signature hash
            callback: Callback function for events
            filter_params: Optional filter parameters
            
        Returns:
            Subscription ID
            
        Raises:
            ConnectionError: If WebSocket not available
        """
        if not self.sapphire_websocket_manager:
            raise ConnectionError("Sapphire WebSocket manager not available")
        
        return await self.sapphire_websocket_manager.subscribe_to_events(
            contract_address=contract_address,
            event_signature=event_signature,
            callback=callback,
            filter_params=filter_params
        )
    
    async def unsubscribe_from_events(self, subscription_id: str, chain: str = "base") -> bool:
        """Unsubscribe from events.
        
        Args:
            subscription_id: Subscription ID to cancel
            chain: Chain name ("base" or "sapphire")
            
        Returns:
            True if successfully unsubscribed
        """
        if chain == "base" and self.base_websocket_manager:
            return await self.base_websocket_manager.unsubscribe_from_events(subscription_id)
        elif chain == "sapphire" and self.sapphire_websocket_manager:
            return await self.sapphire_websocket_manager.unsubscribe_from_events(subscription_id)
        else:
            return False
    
    # Helper Access Methods
    
    @property
    def base(self) -> Optional[Web3Helpers]:
        """Get Base chain helpers."""
        return self.base_helpers
    
    @property  
    def sapphire(self) -> Optional[Web3Helpers]:
        """Get Sapphire chain helpers."""
        return self.sapphire_helpers
    
    # Health Monitoring Methods
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of all components.
        
        Returns:
            Health status information
        """
        health_status = {
            "overall_healthy": True,
            "base_chain": {},
            "sapphire_chain": {},
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Base chain health
        try:
            if self.base_connection_manager:
                base_stats = self.base_connection_manager.get_connection_stats()
                health_status["base_chain"]["connection_manager"] = base_stats
                
                if self.base_helpers:
                    base_health = await self.base_helpers.health_check()
                    health_status["base_chain"]["health"] = base_health
                    if not base_health["healthy"]:
                        health_status["overall_healthy"] = False
            
            if self.base_connection_pool:
                pool_stats = self.base_connection_pool.get_pool_stats()
                health_status["base_chain"]["connection_pool"] = pool_stats
            
            if self.base_websocket_manager:
                ws_info = self.base_websocket_manager.get_connection_info()
                health_status["base_chain"]["websocket"] = ws_info
                if not self.base_websocket_manager.is_connected:
                    health_status["overall_healthy"] = False
                    
        except Exception as e:
            health_status["base_chain"]["error"] = str(e)
            health_status["overall_healthy"] = False
        
        # Sapphire chain health
        try:
            if self.sapphire_connection_manager:
                sapphire_stats = self.sapphire_connection_manager.get_connection_stats()
                health_status["sapphire_chain"]["connection_manager"] = sapphire_stats
                
                if self.sapphire_helpers:
                    sapphire_health = await self.sapphire_helpers.health_check()
                    health_status["sapphire_chain"]["health"] = sapphire_health
                    if not sapphire_health["healthy"]:
                        health_status["overall_healthy"] = False
            
            if self.sapphire_connection_pool:
                pool_stats = self.sapphire_connection_pool.get_pool_stats()
                health_status["sapphire_chain"]["connection_pool"] = pool_stats
            
            if self.sapphire_websocket_manager:
                ws_info = self.sapphire_websocket_manager.get_connection_info()
                health_status["sapphire_chain"]["websocket"] = ws_info
                if not self.sapphire_websocket_manager.is_connected:
                    health_status["overall_healthy"] = False
                    
        except Exception as e:
            health_status["sapphire_chain"]["error"] = str(e)
            health_status["overall_healthy"] = False
        
        return health_status
    
    # Connection Status Methods
    
    @property
    def is_base_connected(self) -> bool:
        """Check if Base chain is connected."""
        if self.base_connection_manager:
            return self.base_connection_manager.is_connected
        return False
    
    @property
    def is_sapphire_connected(self) -> bool:
        """Check if Sapphire chain is connected."""
        if self.sapphire_connection_manager:
            return self.sapphire_connection_manager.is_connected
        return False
    
    @property
    def is_base_websocket_connected(self) -> bool:
        """Check if Base WebSocket is connected."""
        if self.base_websocket_manager:
            return self.base_websocket_manager.is_connected
        return False
    
    @property
    def is_sapphire_websocket_connected(self) -> bool:
        """Check if Sapphire WebSocket is connected."""
        if self.sapphire_websocket_manager:
            return self.sapphire_websocket_manager.is_connected
        return False
    
    @property
    def is_fully_connected(self) -> bool:
        """Check if all required connections are established."""
        return (
            self.is_base_connected and 
            self.is_sapphire_connected and
            (not self.base_config.websocket_urls or self.is_base_websocket_connected) and
            (not self.sapphire_config.websocket_urls or self.is_sapphire_websocket_connected)
        )
    
    # Metrics and Statistics
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all components.
        
        Returns:
            Complete statistics dictionary
        """
        stats = {
            "base_chain": {},
            "sapphire_chain": {},
            "overall": {
                "is_fully_connected": self.is_fully_connected,
                "connection_pool_enabled": self.enable_connection_pool,
            }
        }
        
        # Base chain stats
        if self.base_connection_manager:
            stats["base_chain"]["connection_manager"] = self.base_connection_manager.get_connection_stats()
        
        if self.base_connection_pool:
            stats["base_chain"]["connection_pool"] = self.base_connection_pool.get_pool_stats()
        
        if self.base_websocket_manager:
            stats["base_chain"]["websocket"] = self.base_websocket_manager.get_connection_info()
        
        # Sapphire chain stats
        if self.sapphire_connection_manager:
            stats["sapphire_chain"]["connection_manager"] = self.sapphire_connection_manager.get_connection_stats()
        
        if self.sapphire_connection_pool:
            stats["sapphire_chain"]["connection_pool"] = self.sapphire_connection_pool.get_pool_stats()
        
        if self.sapphire_websocket_manager:
            stats["sapphire_chain"]["websocket"] = self.sapphire_websocket_manager.get_connection_info()
        
        return stats


# Convenience functions for creating pre-configured instances

async def create_web3_integration_from_config(
    base_config: Web3Config,
    sapphire_config: Web3Config, 
    monitoring_config: MonitoringConfig,
    **kwargs
) -> Web3Integration:
    """Create and initialize Web3Integration from configuration.
    
    Args:
        base_config: Base chain configuration
        sapphire_config: Sapphire chain configuration
        monitoring_config: Monitoring configuration
        **kwargs: Additional arguments for Web3Integration
        
    Returns:
        Initialized Web3Integration instance
    """
    integration = Web3Integration(
        base_chain_config=base_config,
        sapphire_chain_config=sapphire_config,
        monitoring_config=monitoring_config,
        **kwargs
    )
    
    await integration.initialize()
    return integration