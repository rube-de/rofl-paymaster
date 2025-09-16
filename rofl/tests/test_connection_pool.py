"""Tests for connection pool module."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock
from web3 import Web3, AsyncWeb3
from web3.exceptions import Web3Exception

from rofl_paymaster.connection_pool import ConnectionPool, PooledConnection
from rofl_paymaster.config import Web3Config


@pytest.fixture
def mock_web3_config():
    """Mock Web3 configuration."""
    return Web3Config(
        rpc_urls=[
            "https://mainnet.base.org",
            "https://base-mainnet.public.blastapi.io",
        ],
        chain_id=8453,
        timeout=30,
        max_retries=3,
        retry_delay=1.0,
    )


@pytest.fixture
def connection_pool(mock_web3_config):
    """Create connection pool instance."""
    return ConnectionPool(
        config=mock_web3_config,
        chain_name="test_chain",
        min_connections=1,
        max_connections=5,
        max_connection_age=300.0,
        max_idle_time=60.0,
    )


class TestPooledConnection:
    """Test PooledConnection class."""
    
    def test_pooled_connection_initialization(self):
        """Test PooledConnection initialization."""
        web3 = Mock()
        async_web3 = AsyncMock()
        current_time = time.time()
        
        connection = PooledConnection(
            web3=web3,
            async_web3=async_web3,
            created_at=current_time,
            last_used=current_time,
            provider_url="https://test.example.com"
        )
        
        assert connection.web3 == web3
        assert connection.async_web3 == async_web3
        assert connection.created_at == current_time
        assert connection.last_used == current_time
        assert connection.usage_count == 0
        assert not connection.is_busy
        assert connection.provider_url == "https://test.example.com"
    
    def test_connection_expiry_check(self):
        """Test connection expiry checking."""
        current_time = time.time()
        old_time = current_time - 400  # 400 seconds ago
        
        connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=old_time,
            last_used=current_time,
            provider_url="https://test.example.com"
        )
        
        # Connection should be expired (max_age = 300 seconds)
        assert connection.is_expired(300.0)
        assert not connection.is_expired(500.0)
    
    def test_connection_idle_check(self):
        """Test connection idle checking."""
        current_time = time.time()
        old_time = current_time - 120  # 120 seconds ago
        
        connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=old_time,
            provider_url="https://test.example.com"
        )
        
        # Connection should be idle (max_idle = 60 seconds)
        assert connection.is_idle(60.0)
        assert not connection.is_idle(180.0)


class TestConnectionPool:
    """Test ConnectionPool class."""
    
    def test_initialization(self, connection_pool):
        """Test connection pool initialization."""
        assert connection_pool.chain_name == "test_chain"
        assert connection_pool.min_connections == 1
        assert connection_pool.max_connections == 5
        assert connection_pool.max_connection_age == 300.0
        assert connection_pool.max_idle_time == 60.0
        assert len(connection_pool.pools) == 2  # Two RPC URLs
        assert connection_pool.total_connections == 0
        assert connection_pool.created_connections == 0
        assert connection_pool.destroyed_connections == 0
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.connection_pool.HTTPProvider')
    @patch('rofl_paymaster.connection_pool.AsyncHTTPProvider')
    @patch('rofl_paymaster.connection_pool.Web3')
    @patch('rofl_paymaster.connection_pool.AsyncWeb3')
    async def test_create_connection_success(
        self, mock_async_web3, mock_web3, mock_async_provider, mock_provider, connection_pool
    ):
        """Test successful connection creation."""
        # Setup mocks
        mock_web3_instance = Mock()
        mock_web3_instance.eth.chain_id = 8453
        mock_web3.return_value = mock_web3_instance
        
        mock_async_web3_instance = AsyncMock()
        mock_async_web3_instance.eth.chain_id = 8453
        mock_async_web3.return_value = mock_async_web3_instance
        
        # Test connection creation
        connection = await connection_pool._create_connection("https://test.example.com")
        
        assert connection is not None
        assert connection.web3 == mock_web3_instance
        assert connection.async_web3 == mock_async_web3_instance
        assert connection.provider_url == "https://test.example.com"
        assert connection_pool.created_connections == 1
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.connection_pool.HTTPProvider')
    @patch('rofl_paymaster.connection_pool.AsyncHTTPProvider')
    @patch('rofl_paymaster.connection_pool.Web3')
    @patch('rofl_paymaster.connection_pool.AsyncWeb3')
    async def test_create_connection_chain_id_mismatch(
        self, mock_async_web3, mock_web3, mock_async_provider, mock_provider, connection_pool
    ):
        """Test connection creation with chain ID mismatch."""
        # Setup mocks with wrong chain ID
        mock_async_web3_instance = AsyncMock()
        mock_async_web3_instance.eth.chain_id = 1  # Wrong chain ID
        mock_async_web3.return_value = mock_async_web3_instance
        
        # Test connection creation
        connection = await connection_pool._create_connection("https://test.example.com")
        
        assert connection is None
        assert connection_pool.created_connections == 0
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.connection_pool.HTTPProvider')
    @patch('rofl_paymaster.connection_pool.AsyncHTTPProvider')
    @patch('rofl_paymaster.connection_pool.Web3')
    @patch('rofl_paymaster.connection_pool.AsyncWeb3')
    async def test_create_connection_timeout(
        self, mock_async_web3, mock_web3, mock_async_provider, mock_provider, connection_pool
    ):
        """Test connection creation timeout."""
        # Setup mocks with timeout - since chain_id is not awaited, we need to make the property access itself raise TimeoutError
        mock_async_web3_instance = AsyncMock()
        # Create a property that raises TimeoutError when accessed
        type(mock_async_web3_instance.eth).chain_id = PropertyMock(side_effect=asyncio.TimeoutError())
        mock_async_web3.return_value = mock_async_web3_instance
        
        # Test connection creation
        connection = await connection_pool._create_connection("https://test.example.com")
        
        assert connection is None
        # Timeout errors are handled separately and don't increment connection_errors
        assert connection_pool.connection_errors == 0
    
    @pytest.mark.asyncio
    async def test_test_connection_health_success(self, connection_pool):
        """Test connection health testing success."""
        # Create mock connection
        mock_async_web3 = AsyncMock()
        mock_async_web3.eth.block_number = 12345
        
        connection = PooledConnection(
            web3=Mock(),
            async_web3=mock_async_web3,
            created_at=time.time(),
            last_used=time.time(),
            provider_url="https://test.example.com"
        )
        
        # Test health check
        is_healthy = await connection_pool._test_connection_health(connection)
        
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_test_connection_health_failure(self, connection_pool):
        """Test connection health testing failure."""
        # Create mock connection that fails
        mock_async_web3 = AsyncMock()
        type(mock_async_web3.eth).block_number = PropertyMock(side_effect=Web3Exception("Connection failed"))
        
        connection = PooledConnection(
            web3=Mock(),
            async_web3=mock_async_web3,
            created_at=time.time(),
            last_used=time.time(),
            provider_url="https://test.example.com"
        )
        
        # Test health check
        is_healthy = await connection_pool._test_connection_health(connection)
        
        assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_initialize(self, connection_pool):
        """Test connection pool initialization."""
        with patch.object(connection_pool, '_create_connection') as mock_create:
            # Mock successful connection creation
            mock_connection = Mock()
            mock_create.return_value = mock_connection
            
            await connection_pool.initialize()
            
            # Should create min_connections for each provider
            assert mock_create.call_count == 2  # 2 providers * 1 min_connection
            assert connection_pool.total_connections == 2
            assert connection_pool._cleanup_task is not None
    
    @pytest.mark.asyncio
    async def test_shutdown(self, connection_pool):
        """Test connection pool shutdown."""
        # Setup some state
        connection_pool._cleanup_task = Mock()
        connection_pool._cleanup_task.cancel = Mock()
        
        # Add some mock connections
        mock_connection = Mock()
        connection_pool.pools["https://mainnet.base.org"].append(mock_connection)
        connection_pool.total_connections = 1
        
        with patch.object(connection_pool, '_destroy_connection') as mock_destroy:
            await connection_pool.shutdown()
            
            connection_pool._cleanup_task.cancel.assert_called_once()
            mock_destroy.assert_called_once_with(mock_connection)
            assert connection_pool.total_connections == 0
    
    @pytest.mark.asyncio
    async def test_get_connection_from_pool_success(self, connection_pool):
        """Test getting connection from pool successfully."""
        # Create a healthy connection in the pool
        current_time = time.time()
        provider_url = "https://mainnet.base.org"  # Use URL from fixture config
        mock_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=current_time,
            provider_url=provider_url
        )
        
        connection_pool.pools[provider_url].append(mock_connection)
        
        with patch.object(connection_pool, '_test_connection_health', return_value=True):
            connection = await connection_pool._get_connection_from_pool(provider_url)
            
            assert connection == mock_connection
            assert len(connection_pool.pools[provider_url]) == 0  # Removed from pool
    
    @pytest.mark.asyncio
    async def test_get_connection_from_pool_expired_connection(self, connection_pool):
        """Test getting connection from pool with expired connection."""
        # Create an expired connection
        old_time = time.time() - 400  # 400 seconds ago
        provider_url = "https://mainnet.base.org"  # Use URL from fixture config
        mock_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=old_time,
            last_used=old_time,
            provider_url=provider_url
        )
        
        connection_pool.pools[provider_url].append(mock_connection)
        connection_pool.active_connections[provider_url] = 1
        connection_pool.total_connections = 1
        
        with patch.object(connection_pool, '_destroy_connection') as mock_destroy:
            connection = await connection_pool._get_connection_from_pool(provider_url)
            
            assert connection is None
            mock_destroy.assert_called_once_with(mock_connection)
            assert connection_pool.active_connections[provider_url] == 0
            assert connection_pool.total_connections == 0
    
    @pytest.mark.asyncio
    async def test_get_connection_context_manager(self, connection_pool):
        """Test get_connection context manager."""
        # Setup mock connection
        current_time = time.time()
        mock_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=current_time,
            provider_url="https://test.example.com"
        )
        
        with patch.object(connection_pool, '_acquire_connection', return_value=mock_connection) as mock_acquire, \
             patch.object(connection_pool, '_release_connection') as mock_release:
            
            async with connection_pool.get_connection() as connection:
                assert connection == mock_connection
                assert connection.is_busy
                assert connection.usage_count == 1
            
            mock_acquire.assert_called_once()
            mock_release.assert_called_once_with(mock_connection)
            assert not connection.is_busy
    
    @pytest.mark.asyncio
    async def test_get_connection_no_available_connections(self, connection_pool):
        """Test get_connection when no connections available."""
        with patch.object(connection_pool, '_acquire_connection', return_value=None):
            with pytest.raises(ConnectionError, match="Unable to acquire connection from pool"):
                async with connection_pool.get_connection():
                    pass
    
    @pytest.mark.asyncio
    async def test_acquire_connection_from_pool(self, connection_pool):
        """Test acquiring connection from pool."""
        # Setup mock connection in pool
        current_time = time.time()
        mock_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=current_time,
            provider_url="https://mainnet.base.org"
        )
        
        connection_pool.pools["https://mainnet.base.org"].append(mock_connection)
        
        with patch.object(connection_pool, '_get_connection_from_pool', return_value=mock_connection):
            connection = await connection_pool._acquire_connection()
            
            assert connection == mock_connection
            assert connection_pool.pool_hits == 1
    
    @pytest.mark.asyncio
    async def test_acquire_connection_create_new(self, connection_pool):
        """Test acquiring connection by creating new one."""
        # No connections in pool
        current_time = time.time()
        mock_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=current_time,
            provider_url="https://mainnet.base.org"
        )
        
        with patch.object(connection_pool, '_get_connection_from_pool', return_value=None), \
             patch.object(connection_pool, '_create_connection', return_value=mock_connection):
            
            connection = await connection_pool._acquire_connection()
            
            assert connection == mock_connection
            assert connection_pool.pool_misses == 1
            assert connection_pool.active_connections["https://mainnet.base.org"] == 1
            assert connection_pool.total_connections == 1
    
    @pytest.mark.asyncio
    async def test_release_connection_healthy(self, connection_pool):
        """Test releasing healthy connection back to pool."""
        current_time = time.time()
        mock_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=current_time,
            provider_url="https://mainnet.base.org"
        )
        
        with patch.object(connection_pool, '_test_connection_health', return_value=True):
            await connection_pool._release_connection(mock_connection)
            
            # Connection should be returned to pool
            assert len(connection_pool.pools["https://mainnet.base.org"]) == 1
            assert connection_pool.pools["https://mainnet.base.org"][0] == mock_connection
    
    @pytest.mark.asyncio
    async def test_release_connection_unhealthy(self, connection_pool):
        """Test releasing unhealthy connection."""
        current_time = time.time()
        mock_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=current_time,
            provider_url="https://mainnet.base.org"
        )
        
        connection_pool.active_connections["https://mainnet.base.org"] = 1
        connection_pool.total_connections = 1
        
        with patch.object(connection_pool, '_test_connection_health', return_value=False), \
             patch.object(connection_pool, '_destroy_connection') as mock_destroy:
            
            await connection_pool._release_connection(mock_connection)
            
            # Connection should be destroyed, not returned to pool
            assert len(connection_pool.pools["https://mainnet.base.org"]) == 0
            mock_destroy.assert_called_once_with(mock_connection)
            assert connection_pool.active_connections["https://mainnet.base.org"] == 0
            assert connection_pool.total_connections == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_connections(self, connection_pool):
        """Test cleanup of expired connections."""
        # Create expired connection
        old_time = time.time() - 400  # 400 seconds ago
        expired_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=old_time,
            last_used=old_time,
            provider_url="https://mainnet.base.org"
        )
        
        # Create healthy connection
        current_time = time.time()
        healthy_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=current_time,
            provider_url="https://mainnet.base.org"
        )
        
        connection_pool.pools["https://mainnet.base.org"].extend([expired_connection, healthy_connection])
        connection_pool.active_connections["https://mainnet.base.org"] = 2
        connection_pool.total_connections = 2
        
        with patch.object(connection_pool, '_destroy_connection') as mock_destroy:
            await connection_pool._cleanup_expired_connections()
            
            # Only expired connection should be destroyed
            mock_destroy.assert_called_once_with(expired_connection)
            assert len(connection_pool.pools["https://mainnet.base.org"]) == 1
            assert connection_pool.pools["https://mainnet.base.org"][0] == healthy_connection
            assert connection_pool.active_connections["https://mainnet.base.org"] == 1
            assert connection_pool.total_connections == 1
    
    @pytest.mark.asyncio
    async def test_maintain_minimum_connections(self, connection_pool):
        """Test maintaining minimum connections."""
        # Start with no connections
        assert connection_pool.total_connections == 0
        
        current_time = time.time()
        mock_connection = PooledConnection(
            web3=Mock(),
            async_web3=AsyncMock(),
            created_at=current_time,
            last_used=current_time,
            provider_url="https://mainnet.base.org"
        )
        
        with patch.object(connection_pool, '_create_connection', return_value=mock_connection):
            await connection_pool._maintain_minimum_connections()
            
            # Should create min_connections for each provider
            assert connection_pool.total_connections == 2  # 2 providers * 1 min_connection
    
    def test_get_pool_stats(self, connection_pool):
        """Test pool statistics."""
        # Setup some state
        connection_pool.total_connections = 5
        connection_pool.created_connections = 10
        connection_pool.destroyed_connections = 5
        connection_pool.pool_hits = 20
        connection_pool.pool_misses = 5
        connection_pool.connection_errors = 2
        
        # Add some connections to pools
        mock_connection = Mock()
        connection_pool.pools["https://mainnet.base.org"].append(mock_connection)
        connection_pool.active_connections["https://mainnet.base.org"] = 2
        
        stats = connection_pool.get_pool_stats()
        
        assert stats["chain_name"] == "test_chain"
        assert stats["total_connections"] == 5
        assert stats["created_connections"] == 10
        assert stats["destroyed_connections"] == 5
        assert stats["pool_hits"] == 20
        assert stats["pool_misses"] == 5
        assert stats["connection_errors"] == 2
        assert stats["hit_rate"] == 0.8  # 20/(20+5)
        
        # Check provider stats
        assert stats["providers"]["https://mainnet.base.org"]["available"] == 1
        assert stats["providers"]["https://mainnet.base.org"]["active"] == 2
        assert stats["providers"]["https://mainnet.base.org"]["total"] == 3