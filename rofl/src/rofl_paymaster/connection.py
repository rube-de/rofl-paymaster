"""Connection management for Web3 providers with failover and health checking."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum

from web3 import Web3, AsyncWeb3
from web3.providers import HTTPProvider, WebSocketProvider, AsyncHTTPProvider
from web3.exceptions import Web3Exception
from web3.types import RPCEndpoint, RPCResponse

from .config import Web3Config
from .logging import get_logger


class ConnectionStatus(Enum):
    """Connection status enumeration."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    """Provider health information."""
    
    status: ConnectionStatus = ConnectionStatus.UNKNOWN
    last_check: float = 0.0
    response_time: float = 0.0
    error_count: int = 0
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    
    def is_healthy(self) -> bool:
        """Check if provider is healthy."""
        return self.status == ConnectionStatus.HEALTHY
    
    def is_available(self) -> bool:
        """Check if provider is available (healthy or degraded)."""
        return self.status in (ConnectionStatus.HEALTHY, ConnectionStatus.DEGRADED)


@dataclass
class ProviderInfo:
    """Provider information and metrics."""
    
    url: str
    provider: Optional[Union[HTTPProvider, AsyncHTTPProvider, WebSocketProvider]] = None
    health: ProviderHealth = field(default_factory=ProviderHealth)
    is_websocket: bool = False
    connection_attempts: int = 0
    last_used: float = 0.0
    
    def __post_init__(self):
        """Initialize provider based on URL."""
        self.is_websocket = self.url.startswith(('ws://', 'wss://'))


class ConnectionManager:
    """Manages Web3 connections with failover, health checking, and connection pooling."""
    
    def __init__(self, config: Web3Config, chain_name: str = "unknown"):
        """Initialize connection manager.
        
        Args:
            config: Web3 configuration
            chain_name: Name of the chain for logging purposes
        """
        self.config = config
        self.chain_name = chain_name
        self.logger = get_logger(f"connection.{chain_name}")
        
        # Initialize providers
        self.http_providers: List[ProviderInfo] = []
        self.ws_providers: List[ProviderInfo] = []
        
        # Connection state
        self.current_http_provider: Optional[ProviderInfo] = None
        self.current_ws_provider: Optional[ProviderInfo] = None
        self.web3_instance: Optional[Web3] = None
        self.async_web3_instance: Optional[AsyncWeb3] = None
        
        # Health checking
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval = 30.0  # seconds
        self._health_check_timeout = 10.0   # seconds
        
        # Connection pools
        self._connection_pool: Dict[str, Any] = {}
        self._pool_lock = asyncio.Lock()
        
        # Metrics
        self.total_requests = 0
        self.failed_requests = 0
        self.failover_count = 0
        
        self._setup_providers()
    
    def _setup_providers(self) -> None:
        """Set up HTTP and WebSocket providers from configuration."""
        # Setup HTTP providers
        for url in self.config.rpc_urls:
            provider_info = ProviderInfo(url=url)
            self.http_providers.append(provider_info)
            self.logger.debug(f"Added HTTP provider: {url}")
        
        # Setup WebSocket providers
        if self.config.websocket_urls:
            for url in self.config.websocket_urls:
                provider_info = ProviderInfo(url=url, is_websocket=True)
                self.ws_providers.append(provider_info)
                self.logger.debug(f"Added WebSocket provider: {url}")
    
    async def initialize(self) -> None:
        """Initialize connections and start health checking."""
        self.logger.info(f"Initializing connection manager for {self.chain_name}")
        
        # Initialize HTTP connection
        await self._connect_http()
        
        # Initialize WebSocket connection if available
        if self.ws_providers:
            await self._connect_websocket()
        
        # Start health checking
        await self._start_health_checking()
        
        self.logger.info(f"Connection manager initialized for {self.chain_name}")
    
    async def shutdown(self) -> None:
        """Shutdown connections and cleanup resources."""
        self.logger.info(f"Shutting down connection manager for {self.chain_name}")
        
        # Stop health checking
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                # Only await if it's an actual Task, not a Mock in tests
                if hasattr(self._health_check_task, '__await__'):
                    await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close connections
        await self._close_connections()
        
        self.logger.info(f"Connection manager shut down for {self.chain_name}")
    
    async def _connect_http(self) -> bool:
        """Connect to HTTP provider with failover."""
        for provider_info in self.http_providers:
            try:
                self.logger.debug(f"Attempting HTTP connection to {provider_info.url}")
                
                # Create provider
                provider = HTTPProvider(
                    provider_info.url,
                    request_kwargs={
                        'timeout': self.config.timeout,
                    }
                )
                
                # Create Web3 instance
                web3 = Web3(provider)
                async_provider = AsyncHTTPProvider(
                    provider_info.url,
                    request_kwargs={
                        'timeout': self.config.timeout,
                    }
                )
                async_web3 = AsyncWeb3(async_provider)
                
                # Test connection
                if await self._test_connection(web3, async_web3):
                    provider_info.provider = provider
                    provider_info.health.status = ConnectionStatus.HEALTHY
                    provider_info.connection_attempts += 1
                    
                    self.current_http_provider = provider_info
                    self.web3_instance = web3
                    self.async_web3_instance = async_web3
                    
                    self.logger.info(f"Connected to HTTP provider: {provider_info.url}")
                    return True
                
            except Exception as e:
                provider_info.health.status = ConnectionStatus.FAILED
                provider_info.health.last_error = str(e)
                provider_info.health.consecutive_failures += 1
                self.logger.warning(f"HTTP connection failed for {provider_info.url}: {e}")
        
        self.logger.error("Failed to connect to any HTTP provider")
        return False
    
    async def _connect_websocket(self) -> bool:
        """Connect to WebSocket provider with failover."""
        for provider_info in self.ws_providers:
            try:
                self.logger.debug(f"Attempting WebSocket connection to {provider_info.url}")
                
                # Create WebSocket provider
                provider = WebSocketProvider(provider_info.url)
                
                # Test connection
                web3_ws = Web3(provider)
                if await self._test_websocket_connection(web3_ws):
                    provider_info.provider = provider
                    provider_info.health.status = ConnectionStatus.HEALTHY
                    provider_info.connection_attempts += 1
                    
                    self.current_ws_provider = provider_info
                    
                    self.logger.info(f"Connected to WebSocket provider: {provider_info.url}")
                    return True
                
            except Exception as e:
                provider_info.health.status = ConnectionStatus.FAILED
                provider_info.health.last_error = str(e)
                provider_info.health.consecutive_failures += 1
                self.logger.warning(f"WebSocket connection failed for {provider_info.url}: {e}")
        
        self.logger.error("Failed to connect to any WebSocket provider")
        return False
    
    async def _test_connection(self, web3: Web3, async_web3: AsyncWeb3) -> bool:
        """Test HTTP connection by getting chain ID."""
        try:
            start_time = time.time()
            
            # Test sync connection
            chain_id = web3.eth.chain_id
            if chain_id != self.config.chain_id:
                self.logger.error(
                    f"Chain ID mismatch: expected {self.config.chain_id}, got {chain_id}"
                )
                return False
            
            # Test async connection
            async_chain_id = async_web3.eth.chain_id
            if async_chain_id != self.config.chain_id:
                self.logger.error(
                    f"Async chain ID mismatch: expected {self.config.chain_id}, got {async_chain_id}"
                )
                return False
            
            response_time = time.time() - start_time
            self.logger.debug(f"Connection test successful, response time: {response_time:.3f}s")
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Connection test failed: {e}")
            return False
    
    async def _test_websocket_connection(self, web3: Web3) -> bool:
        """Test WebSocket connection."""
        try:
            start_time = time.time()
            
            # Test connection by getting chain ID
            chain_id = web3.eth.chain_id
            if chain_id != self.config.chain_id:
                self.logger.error(
                    f"WebSocket chain ID mismatch: expected {self.config.chain_id}, got {chain_id}"
                )
                return False
            
            response_time = time.time() - start_time
            self.logger.debug(f"WebSocket test successful, response time: {response_time:.3f}s")
            
            return True
            
        except Exception as e:
            self.logger.debug(f"WebSocket test failed: {e}")
            return False
    
    async def _start_health_checking(self) -> None:
        """Start background health checking task."""
        if self._health_check_task:
            return
        
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self.logger.debug("Started health checking task")
    
    async def _health_check_loop(self) -> None:
        """Background health checking loop."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._check_all_providers_health()
                await self._handle_unhealthy_connections()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
    
    async def _check_all_providers_health(self) -> None:
        """Check health of all providers."""
        # Check HTTP providers
        for provider_info in self.http_providers:
            await self._check_provider_health(provider_info)
        
        # Check WebSocket providers
        for provider_info in self.ws_providers:
            await self._check_provider_health(provider_info)
    
    async def _check_provider_health(self, provider_info: ProviderInfo) -> None:
        """Check health of a specific provider."""
        if not provider_info.provider:
            return
        
        try:
            start_time = time.time()
            
            if provider_info.is_websocket:
                # For WebSocket, just check if connection is alive
                web3 = Web3(provider_info.provider)
                chain_id = web3.eth.chain_id
            else:
                # For HTTP, use the current Web3 instance if it matches
                if (self.current_http_provider == provider_info and 
                    self.web3_instance and self.async_web3_instance):
                    chain_id = self.async_web3_instance.eth.chain_id
                else:
                    # Create temporary connection for health check
                    async_provider = AsyncHTTPProvider(
                        provider_info.url,
                        request_kwargs={'timeout': self._health_check_timeout}
                    )
                    async_web3 = AsyncWeb3(async_provider)
                    chain_id = async_web3.eth.chain_id
            
            response_time = time.time() - start_time
            
            # Update health status
            provider_info.health.last_check = time.time()
            provider_info.health.response_time = response_time
            provider_info.health.consecutive_failures = 0
            
            # Determine status based on response time
            if response_time < 2.0:
                provider_info.health.status = ConnectionStatus.HEALTHY
            elif response_time < 5.0:
                provider_info.health.status = ConnectionStatus.DEGRADED
            else:
                provider_info.health.status = ConnectionStatus.FAILED
            
            if chain_id != self.config.chain_id:
                provider_info.health.status = ConnectionStatus.FAILED
                provider_info.health.last_error = f"Chain ID mismatch: {chain_id}"
            
        except Exception as e:
            provider_info.health.status = ConnectionStatus.FAILED
            provider_info.health.last_check = time.time()
            provider_info.health.consecutive_failures += 1
            provider_info.health.error_count += 1
            provider_info.health.last_error = str(e)
            
            self.logger.debug(f"Health check failed for {provider_info.url}: {e}")
    
    async def _handle_unhealthy_connections(self) -> None:
        """Handle unhealthy connections by attempting failover."""
        # Check if current HTTP provider is unhealthy
        if (self.current_http_provider and 
            not self.current_http_provider.health.is_available()):
            
            self.logger.warning(
                f"Current HTTP provider unhealthy: {self.current_http_provider.url}, "
                f"attempting failover"
            )
            await self._failover_http()
        
        # Check if current WebSocket provider is unhealthy
        if (self.current_ws_provider and 
            not self.current_ws_provider.health.is_available()):
            
            self.logger.warning(
                f"Current WebSocket provider unhealthy: {self.current_ws_provider.url}, "
                f"attempting failover"
            )
            await self._failover_websocket()
    
    async def _failover_http(self) -> bool:
        """Failover to a healthy HTTP provider."""
        # Find healthy providers
        healthy_providers = [
            p for p in self.http_providers 
            if p != self.current_http_provider and p.health.is_available()
        ]
        
        if not healthy_providers:
            # Try to reconnect to failed providers
            self.logger.warning("No healthy HTTP providers available, attempting reconnection")
            return await self._connect_http()
        
        # Sort by health status and response time
        healthy_providers.sort(
            key=lambda p: (
                p.health.status != ConnectionStatus.HEALTHY,
                p.health.response_time
            )
        )
        
        # Try to connect to the best provider
        best_provider = healthy_providers[0]
        old_provider = self.current_http_provider
        
        try:
            # Create new connections
            provider = HTTPProvider(
                best_provider.url,
                request_kwargs={'timeout': self.config.timeout}
            )
            async_provider = AsyncHTTPProvider(
                best_provider.url,
                request_kwargs={'timeout': self.config.timeout}
            )
            
            web3 = Web3(provider)
            async_web3 = AsyncWeb3(async_provider)
            
            # Test new connection
            if await self._test_connection(web3, async_web3):
                # Switch to new provider
                best_provider.provider = provider
                self.current_http_provider = best_provider
                self.web3_instance = web3
                self.async_web3_instance = async_web3
                self.failover_count += 1
                
                self.logger.info(
                    f"HTTP failover successful: {old_provider.url if old_provider else 'None'} "
                    f"-> {best_provider.url}"
                )
                return True
            
        except Exception as e:
            best_provider.health.status = ConnectionStatus.FAILED
            best_provider.health.last_error = str(e)
            self.logger.error(f"HTTP failover failed to {best_provider.url}: {e}")
        
        return False
    
    async def _failover_websocket(self) -> bool:
        """Failover to a healthy WebSocket provider."""
        # Find healthy providers
        healthy_providers = [
            p for p in self.ws_providers 
            if p != self.current_ws_provider and p.health.is_available()
        ]
        
        if not healthy_providers:
            # Try to reconnect to failed providers
            self.logger.warning("No healthy WebSocket providers available, attempting reconnection")
            return await self._connect_websocket()
        
        # Sort by health status and response time
        healthy_providers.sort(
            key=lambda p: (
                p.health.status != ConnectionStatus.HEALTHY,
                p.health.response_time
            )
        )
        
        # Try to connect to the best provider
        best_provider = healthy_providers[0]
        old_provider = self.current_ws_provider
        
        try:
            # Create new WebSocket connection
            provider = WebSocketProvider(best_provider.url)
            web3_ws = Web3(provider)
            
            # Test new connection
            if await self._test_websocket_connection(web3_ws):
                # Switch to new provider
                best_provider.provider = provider
                self.current_ws_provider = best_provider
                self.failover_count += 1
                
                self.logger.info(
                    f"WebSocket failover successful: {old_provider.url if old_provider else 'None'} "
                    f"-> {best_provider.url}"
                )
                return True
            
        except Exception as e:
            best_provider.health.status = ConnectionStatus.FAILED
            best_provider.health.last_error = str(e)
            self.logger.error(f"WebSocket failover failed to {best_provider.url}: {e}")
        
        return False
    
    async def _close_connections(self) -> None:
        """Close all connections."""
        # Close HTTP connections
        if self.web3_instance:
            try:
                # Web3.py doesn't have explicit close for HTTP
                self.web3_instance = None
                self.async_web3_instance = None
            except Exception as e:
                self.logger.error(f"Error closing HTTP connection: {e}")
        
        # Close WebSocket connections
        for provider_info in self.ws_providers:
            if provider_info.provider:
                try:
                    # Close WebSocket connection
                    if hasattr(provider_info.provider, 'disconnect'):
                        await provider_info.provider.disconnect()
                except Exception as e:
                    self.logger.error(f"Error closing WebSocket connection: {e}")
        
        # Clear connection pool
        async with self._pool_lock:
            self._connection_pool.clear()
    
    @property
    def web3(self) -> Optional[Web3]:
        """Get the current Web3 instance."""
        return self.web3_instance
    
    @property
    def async_web3(self) -> Optional[AsyncWeb3]:
        """Get the current AsyncWeb3 instance."""
        return self.async_web3_instance
    
    @property
    def is_connected(self) -> bool:
        """Check if HTTP connection is available."""
        return (
            self.current_http_provider is not None and
            self.current_http_provider.health.is_available() and
            self.web3_instance is not None
        )
    
    @property
    def is_websocket_connected(self) -> bool:
        """Check if WebSocket connection is available."""
        return (
            self.current_ws_provider is not None and
            self.current_ws_provider.health.is_available()
        )
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "chain_name": self.chain_name,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "failover_count": self.failover_count,
            "current_http_provider": (
                self.current_http_provider.url if self.current_http_provider else None
            ),
            "current_ws_provider": (
                self.current_ws_provider.url if self.current_ws_provider else None
            ),
            "http_providers": [
                {
                    "url": p.url,
                    "status": p.health.status.value,
                    "response_time": p.health.response_time,
                    "error_count": p.health.error_count,
                    "consecutive_failures": p.health.consecutive_failures,
                    "last_error": p.health.last_error,
                }
                for p in self.http_providers
            ],
            "ws_providers": [
                {
                    "url": p.url,
                    "status": p.health.status.value,
                    "response_time": p.health.response_time,
                    "error_count": p.health.error_count,
                    "consecutive_failures": p.health.consecutive_failures,
                    "last_error": p.health.last_error,
                }
                for p in self.ws_providers
            ],
        }
    
    @asynccontextmanager
    async def get_connection(self, prefer_websocket: bool = False) -> AsyncIterator[Web3]:
        """Get a connection with automatic retry and failover.
        
        Args:
            prefer_websocket: Prefer WebSocket connection if available
            
        Yields:
            Web3 instance
            
        Raises:
            ConnectionError: If no healthy connection is available
        """
        if prefer_websocket and self.is_websocket_connected:
            web3_instance = Web3(self.current_ws_provider.provider)
        elif self.is_connected:
            web3_instance = self.web3_instance
        else:
            # Try to reconnect
            if not await self._connect_http():
                raise ConnectionError("No healthy connections available")
            web3_instance = self.web3_instance
        
        try:
            self.total_requests += 1
            if self.current_http_provider:
                self.current_http_provider.last_used = time.time()
            yield web3_instance
            
        except Exception as e:
            self.failed_requests += 1
            self.logger.error(f"Request failed: {e}")
            
            # Trigger health check
            if self.current_http_provider:
                await self._check_provider_health(self.current_http_provider)
            
            raise