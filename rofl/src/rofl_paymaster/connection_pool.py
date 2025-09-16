"""Advanced connection pooling for Web3 providers."""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, AsyncIterator, Any
from dataclasses import dataclass
from collections import deque

from web3 import Web3, AsyncWeb3
from web3.providers import HTTPProvider, AsyncHTTPProvider

from .config import Web3Config
from .logging import get_logger


@dataclass
class PooledConnection:
    """A pooled Web3 connection."""
    
    web3: Web3
    async_web3: AsyncWeb3
    created_at: float
    last_used: float
    usage_count: int = 0
    is_busy: bool = False
    provider_url: str = ""
    
    def is_expired(self, max_age: float) -> bool:
        """Check if connection has expired."""
        return time.time() - self.created_at > max_age
    
    def is_idle(self, max_idle: float) -> bool:
        """Check if connection has been idle too long."""
        return time.time() - self.last_used > max_idle


class ConnectionPool:
    """Advanced connection pool for Web3 providers."""
    
    def __init__(
        self, 
        config: Web3Config, 
        chain_name: str = "unknown",
        min_connections: int = 2,
        max_connections: int = 10,
        max_connection_age: float = 3600.0,  # 1 hour
        max_idle_time: float = 300.0,        # 5 minutes
        connection_timeout: float = 30.0,
    ):
        """Initialize connection pool.
        
        Args:
            config: Web3 configuration
            chain_name: Name of the chain for logging
            min_connections: Minimum number of connections to maintain
            max_connections: Maximum number of connections allowed
            max_connection_age: Maximum age of a connection in seconds
            max_idle_time: Maximum idle time before closing connection
            connection_timeout: Timeout for creating new connections
        """
        self.config = config
        self.chain_name = chain_name
        self.logger = get_logger(f"connection_pool.{chain_name}")
        
        # Pool configuration
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.max_connection_age = max_connection_age
        self.max_idle_time = max_idle_time
        self.connection_timeout = connection_timeout
        
        # Connection pools per provider URL
        self.pools: Dict[str, deque[PooledConnection]] = {}
        self.active_connections: Dict[str, int] = {}
        self.total_connections = 0
        
        # Pool management
        self._pool_lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 60.0  # Cleanup every minute
        
        # Metrics
        self.created_connections = 0
        self.destroyed_connections = 0
        self.pool_hits = 0
        self.pool_misses = 0
        self.connection_errors = 0
        
        # Initialize pools for each provider
        for url in self.config.rpc_urls:
            self.pools[url] = deque()
            self.active_connections[url] = 0
    
    async def initialize(self) -> None:
        """Initialize the connection pool."""
        self.logger.info(f"Initializing connection pool for {self.chain_name}")
        
        # Create minimum connections for each provider
        for url in self.config.rpc_urls:
            for _ in range(self.min_connections):
                try:
                    connection = await self._create_connection(url)
                    if connection:
                        self.pools[url].append(connection)
                        self.total_connections += 1
                except Exception as e:
                    self.logger.warning(f"Failed to create initial connection to {url}: {e}")
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info(
            f"Connection pool initialized with {self.total_connections} connections "
            f"across {len(self.config.rpc_urls)} providers"
        )
    
    async def shutdown(self) -> None:
        """Shutdown the connection pool."""
        self.logger.info(f"Shutting down connection pool for {self.chain_name}")
        
        # Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                if hasattr(self._cleanup_task, '__await__'):
                    await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        async with self._pool_lock:
            for url, pool in self.pools.items():
                while pool:
                    connection = pool.popleft()
                    await self._destroy_connection(connection)
                self.active_connections[url] = 0
            
            self.total_connections = 0
        
        self.logger.info(f"Connection pool shut down for {self.chain_name}")
    
    @asynccontextmanager
    async def get_connection(self, preferred_provider: Optional[str] = None) -> AsyncIterator[PooledConnection]:
        """Get a connection from the pool.
        
        Args:
            preferred_provider: Preferred provider URL
            
        Yields:
            PooledConnection instance
            
        Raises:
            ConnectionError: If unable to get a connection
        """
        connection = await self._acquire_connection(preferred_provider)
        if not connection:
            raise ConnectionError("Unable to acquire connection from pool")
        
        try:
            connection.is_busy = True
            connection.last_used = time.time()
            connection.usage_count += 1
            yield connection
            
        finally:
            connection.is_busy = False
            await self._release_connection(connection)
    
    async def _acquire_connection(self, preferred_provider: Optional[str] = None) -> Optional[PooledConnection]:
        """Acquire a connection from the pool."""
        async with self._pool_lock:
            # Try preferred provider first
            if preferred_provider and preferred_provider in self.pools:
                connection = await self._get_connection_from_pool(preferred_provider)
                if connection:
                    self.pool_hits += 1
                    return connection
            
            # Try all providers
            for url in self.config.rpc_urls:
                if url == preferred_provider:
                    continue  # Already tried
                
                connection = await self._get_connection_from_pool(url)
                if connection:
                    self.pool_hits += 1
                    return connection
            
            # No available connections, try to create new one
            self.pool_misses += 1
            for url in self.config.rpc_urls:
                if self.active_connections[url] < self.max_connections:
                    connection = await self._create_connection(url)
                    if connection:
                        self.active_connections[url] += 1
                        self.total_connections += 1
                        return connection
            
            self.logger.warning("Unable to acquire connection: pool exhausted")
            return None
    
    async def _get_connection_from_pool(self, provider_url: str) -> Optional[PooledConnection]:
        """Get a connection from a specific provider pool."""
        pool = self.pools[provider_url]
        
        while pool:
            connection = pool.popleft()
            
            # Check if connection is still valid
            if (connection.is_expired(self.max_connection_age) or 
                connection.is_idle(self.max_idle_time)):
                
                await self._destroy_connection(connection)
                self.active_connections[provider_url] -= 1
                self.total_connections -= 1
                continue
            
            # Test connection health
            if await self._test_connection_health(connection):
                return connection
            else:
                # Connection is unhealthy, destroy it
                await self._destroy_connection(connection)
                self.active_connections[provider_url] -= 1
                self.total_connections -= 1
        
        return None
    
    async def _create_connection(self, provider_url: str) -> Optional[PooledConnection]:
        """Create a new connection."""
        try:
            self.logger.debug(f"Creating new connection to {provider_url}")
            
            # Create providers
            http_provider = HTTPProvider(
                provider_url,
                request_kwargs={'timeout': self.config.timeout}
            )
            async_provider = AsyncHTTPProvider(
                provider_url,
                request_kwargs={'timeout': self.config.timeout}
            )
            
            # Create Web3 instances
            web3 = Web3(http_provider)
            async_web3 = AsyncWeb3(async_provider)
            
            # Test connection
            try:
                chain_id = async_web3.eth.chain_id
                
                if chain_id != self.config.chain_id:
                    self.logger.error(
                        f"Chain ID mismatch for {provider_url}: "
                        f"expected {self.config.chain_id}, got {chain_id}"
                    )
                    return None
                
            except asyncio.TimeoutError:
                self.logger.error(f"Connection timeout to {provider_url}")
                return None
            
            connection = PooledConnection(
                web3=web3,
                async_web3=async_web3,
                created_at=time.time(),
                last_used=time.time(),
                provider_url=provider_url
            )
            
            self.created_connections += 1
            self.logger.debug(f"Created connection to {provider_url}")
            
            return connection
            
        except Exception as e:
            self.connection_errors += 1
            self.logger.error(f"Failed to create connection to {provider_url}: {e}")
            return None
    
    async def _destroy_connection(self, connection: PooledConnection) -> None:
        """Destroy a connection."""
        try:
            # Web3.py HTTP connections don't need explicit cleanup
            # Just remove references
            connection.web3 = None
            connection.async_web3 = None
            
            self.destroyed_connections += 1
            self.logger.debug(f"Destroyed connection to {connection.provider_url}")
            
        except Exception as e:
            self.logger.error(f"Error destroying connection: {e}")
    
    async def _release_connection(self, connection: PooledConnection) -> None:
        """Release a connection back to the pool."""
        async with self._pool_lock:
            # Check if connection is still healthy and not expired
            if (not connection.is_expired(self.max_connection_age) and
                await self._test_connection_health(connection)):
                
                # Return to pool
                self.pools[connection.provider_url].append(connection)
                self.logger.debug(f"Released connection to {connection.provider_url}")
            else:
                # Connection is unhealthy or expired, destroy it
                await self._destroy_connection(connection)
                self.active_connections[connection.provider_url] -= 1
                self.total_connections -= 1
                self.logger.debug(f"Destroyed expired/unhealthy connection to {connection.provider_url}")
    
    async def _test_connection_health(self, connection: PooledConnection) -> bool:
        """Test if a connection is healthy."""
        try:
            # Quick health check - get latest block number
            block_number = connection.async_web3.eth.block_number
            # Simple check that we got a valid block number
            if isinstance(block_number, int) and block_number > 0:
                return True
            return False
            
        except Exception as e:
            self.logger.debug(f"Connection health check failed: {e}")
            return False
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired_connections()
                await self._maintain_minimum_connections()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {e}")
    
    async def _cleanup_expired_connections(self) -> None:
        """Clean up expired and idle connections."""
        async with self._pool_lock:
            for url, pool in self.pools.items():
                cleaned = 0
                new_pool = deque()
                
                while pool:
                    connection = pool.popleft()
                    
                    if (connection.is_expired(self.max_connection_age) or 
                        connection.is_idle(self.max_idle_time)):
                        
                        await self._destroy_connection(connection)
                        self.active_connections[url] -= 1
                        self.total_connections -= 1
                        cleaned += 1
                    else:
                        new_pool.append(connection)
                
                self.pools[url] = new_pool
                
                if cleaned > 0:
                    self.logger.debug(f"Cleaned up {cleaned} expired connections for {url}")
    
    async def _maintain_minimum_connections(self) -> None:
        """Maintain minimum number of connections per provider."""
        for url in self.config.rpc_urls:
            current_count = len(self.pools[url]) + self.active_connections[url]
            
            if current_count < self.min_connections:
                needed = self.min_connections - current_count
                
                for _ in range(needed):
                    try:
                        connection = await self._create_connection(url)
                        if connection:
                            async with self._pool_lock:
                                self.pools[url].append(connection)
                                self.total_connections += 1
                                
                    except Exception as e:
                        self.logger.warning(f"Failed to create maintenance connection to {url}: {e}")
                        break  # Don't try to create more if one fails
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        pool_stats = {}
        
        for url in self.config.rpc_urls:
            pool_stats[url] = {
                "available": len(self.pools[url]),
                "active": self.active_connections[url],
                "total": len(self.pools[url]) + self.active_connections[url]
            }
        
        return {
            "chain_name": self.chain_name,
            "total_connections": self.total_connections,
            "created_connections": self.created_connections,
            "destroyed_connections": self.destroyed_connections,
            "pool_hits": self.pool_hits,
            "pool_misses": self.pool_misses,
            "connection_errors": self.connection_errors,
            "hit_rate": self.pool_hits / max(1, self.pool_hits + self.pool_misses),
            "providers": pool_stats,
            "config": {
                "min_connections": self.min_connections,
                "max_connections": self.max_connections,
                "max_connection_age": self.max_connection_age,
                "max_idle_time": self.max_idle_time,
            }
        }