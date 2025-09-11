"""Tests for connection management module."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from web3 import Web3, AsyncWeb3
from web3.exceptions import Web3Exception

from rofl_paymaster.connection import ConnectionManager, ConnectionStatus
from rofl_paymaster.config import Web3Config


@pytest.fixture
def mock_web3_config():
    """Mock Web3 configuration."""
    return Web3Config(
        rpc_urls=[
            "https://mainnet.base.org",
            "https://base-mainnet.public.blastapi.io",
        ],
        websocket_urls=[
            "wss://mainnet.base.org",
            "wss://base-mainnet.public.blastapi.io",
        ],
        chain_id=8453,
        timeout=30,
        max_retries=3,
        retry_delay=1.0,
    )


@pytest.fixture
def connection_manager(mock_web3_config):
    """Create connection manager instance."""
    return ConnectionManager(mock_web3_config, "test_chain")


class TestConnectionManager:
    """Test ConnectionManager class."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, connection_manager):
        """Test connection manager initialization."""
        assert connection_manager.chain_name == "test_chain"
        assert len(connection_manager.http_providers) == 2
        assert len(connection_manager.ws_providers) == 2
        assert connection_manager.current_http_provider is None
        assert connection_manager.current_ws_provider is None
        assert connection_manager.web3_instance is None
        assert connection_manager.async_web3_instance is None
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.connection.HTTPProvider')
    @patch('rofl_paymaster.connection.AsyncHTTPProvider')
    @patch('rofl_paymaster.connection.Web3')
    @patch('rofl_paymaster.connection.AsyncWeb3')
    async def test_http_connection_success(
        self, mock_async_web3, mock_web3, mock_async_provider, mock_provider, connection_manager
    ):
        """Test successful HTTP connection."""
        # Setup mocks
        mock_web3_instance = Mock()
        mock_web3_instance.eth.chain_id = 8453
        mock_web3.return_value = mock_web3_instance
        
        mock_async_web3_instance = AsyncMock()
        mock_async_web3_instance.eth.chain_id = 8453
        mock_async_web3.return_value = mock_async_web3_instance
        
        # Test connection
        result = await connection_manager._connect_http()
        
        assert result is True
        assert connection_manager.current_http_provider is not None
        assert connection_manager.web3_instance == mock_web3_instance
        assert connection_manager.async_web3_instance == mock_async_web3_instance
        assert connection_manager.current_http_provider.health.status == ConnectionStatus.HEALTHY
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.connection.HTTPProvider')
    @patch('rofl_paymaster.connection.AsyncHTTPProvider')
    @patch('rofl_paymaster.connection.Web3')
    @patch('rofl_paymaster.connection.AsyncWeb3')
    async def test_http_connection_chain_id_mismatch(
        self, mock_async_web3, mock_web3, mock_async_provider, mock_provider, connection_manager
    ):
        """Test HTTP connection with chain ID mismatch."""
        # Setup mocks with wrong chain ID
        mock_web3_instance = Mock()
        mock_web3_instance.eth.chain_id = 1  # Wrong chain ID
        mock_web3.return_value = mock_web3_instance
        
        mock_async_web3_instance = AsyncMock()
        mock_async_web3_instance.eth.chain_id = 1  # Wrong chain ID
        mock_async_web3.return_value = mock_async_web3_instance
        
        # Test connection
        result = await connection_manager._connect_http()
        
        assert result is False
        assert connection_manager.current_http_provider is None
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.connection.HTTPProvider')
    @patch('rofl_paymaster.connection.AsyncHTTPProvider')
    @patch('rofl_paymaster.connection.Web3')
    @patch('rofl_paymaster.connection.AsyncWeb3')
    async def test_http_connection_failure_with_failover(
        self, mock_async_web3, mock_web3, mock_async_provider, mock_provider, connection_manager
    ):
        """Test HTTP connection failure with successful failover."""
        # Setup mocks - first provider fails at Web3 creation, second provider succeeds
        web3_call_count = 0
        
        def web3_side_effect(*args, **kwargs):
            nonlocal web3_call_count
            web3_call_count += 1
            if web3_call_count == 1:  # First provider fails
                raise Web3Exception("Connection failed")
            else:  # Second provider succeeds
                mock_web3_instance = Mock()
                mock_web3_instance.eth.chain_id = 8453
                return mock_web3_instance
        
        # For the first call, async should succeed (since sync failed first)
        # For the second call, both should succeed
        mock_async_web3_instance = AsyncMock()
        mock_async_web3_instance.eth.chain_id = 8453
        mock_async_web3.return_value = mock_async_web3_instance
        
        mock_web3.side_effect = web3_side_effect
        
        # Test connection
        result = await connection_manager._connect_http()
        
        assert result is True
        assert connection_manager.current_http_provider is not None
        assert connection_manager.current_http_provider.url == "https://base-mainnet.public.blastapi.io"
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.connection.WebSocketProvider')
    @patch('rofl_paymaster.connection.Web3')
    async def test_websocket_connection_success(
        self, mock_web3, mock_ws_provider, connection_manager
    ):
        """Test successful WebSocket connection."""
        # Setup mocks
        mock_web3_instance = Mock()
        mock_web3_instance.eth.chain_id = 8453
        mock_web3.return_value = mock_web3_instance
        
        # Test connection
        result = await connection_manager._connect_websocket()
        
        assert result is True
        assert connection_manager.current_ws_provider is not None
        assert connection_manager.current_ws_provider.health.status == ConnectionStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_initialize(self, connection_manager):
        """Test connection manager initialization."""
        with patch.object(connection_manager, '_connect_http', return_value=True) as mock_http, \
             patch.object(connection_manager, '_connect_websocket', return_value=True) as mock_ws, \
             patch.object(connection_manager, '_start_health_checking') as mock_health:
            
            await connection_manager.initialize()
            
            mock_http.assert_called_once()
            mock_ws.assert_called_once()
            mock_health.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, connection_manager):
        """Test connection manager shutdown."""
        # Setup some state
        connection_manager._health_check_task = Mock()
        connection_manager._health_check_task.cancel = Mock()
        
        with patch.object(connection_manager, '_close_connections') as mock_close:
            await connection_manager.shutdown()
            
            connection_manager._health_check_task.cancel.assert_called_once()
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.connection.AsyncHTTPProvider')
    @patch('rofl_paymaster.connection.AsyncWeb3')
    async def test_health_check_provider(self, mock_async_web3, mock_async_provider, connection_manager):
        """Test provider health checking."""
        # Create a mock provider info
        from rofl_paymaster.connection import ProviderInfo, ProviderHealth
        
        provider_info = ProviderInfo(url="https://test.example.com")
        provider_info.provider = Mock()
        provider_info.health = ProviderHealth()
        
        # Mock successful health check - setup async web3 mock
        mock_async_web3_instance = AsyncMock()
        mock_async_web3_instance.eth.chain_id = 8453
        mock_async_web3.return_value = mock_async_web3_instance
        
        # Set up connection manager state to use existing instance
        connection_manager.web3_instance = Mock()
        mock_async_instance = AsyncMock()
        mock_async_instance.eth.chain_id = 8453
        connection_manager.async_web3_instance = mock_async_instance
        connection_manager.current_http_provider = provider_info
        
        await connection_manager._check_provider_health(provider_info)
        
        assert provider_info.health.status == ConnectionStatus.HEALTHY
        assert provider_info.health.consecutive_failures == 0
        assert provider_info.health.last_check > 0
    
    @pytest.mark.asyncio
    async def test_health_check_provider_failure(self, connection_manager):
        """Test provider health check failure."""
        from rofl_paymaster.connection import ProviderInfo, ProviderHealth
        
        provider_info = ProviderInfo(url="https://test.example.com")
        provider_info.provider = Mock()
        provider_info.health = ProviderHealth()
        
        # Mock failed health check - chain ID doesn't match expected
        connection_manager.web3_instance = Mock()
        mock_async_instance = AsyncMock()
        mock_async_instance.eth.chain_id = 1  # Wrong chain ID (expected 8453)
        connection_manager.async_web3_instance = mock_async_instance
        connection_manager.current_http_provider = provider_info
        
        await connection_manager._check_provider_health(provider_info)
        
        assert provider_info.health.status == ConnectionStatus.FAILED
        assert "Chain ID mismatch" in provider_info.health.last_error
        assert provider_info.health.consecutive_failures == 0  # Chain ID mismatch is not a connection failure
        assert provider_info.health.error_count == 0
    
    @pytest.mark.asyncio
    async def test_failover_http(self, connection_manager):
        """Test HTTP failover functionality."""
        from rofl_paymaster.connection import ProviderInfo, ProviderHealth, ConnectionStatus
        
        # Setup initial failed provider
        failed_provider = ProviderInfo(url="https://failed.example.com")
        failed_provider.health.status = ConnectionStatus.FAILED
        connection_manager.current_http_provider = failed_provider
        connection_manager.http_providers = [failed_provider]
        
        # Setup healthy backup provider
        healthy_provider = ProviderInfo(url="https://healthy.example.com")
        healthy_provider.health.status = ConnectionStatus.HEALTHY
        healthy_provider.health.response_time = 0.1
        connection_manager.http_providers.append(healthy_provider)
        
        with patch.object(connection_manager, '_test_connection', return_value=True) as mock_test, \
             patch('rofl_paymaster.connection.HTTPProvider') as mock_http_provider, \
             patch('rofl_paymaster.connection.AsyncHTTPProvider') as mock_async_provider, \
             patch('rofl_paymaster.connection.Web3') as mock_web3, \
             patch('rofl_paymaster.connection.AsyncWeb3') as mock_async_web3:
            
            result = await connection_manager._failover_http()
            
            assert result is True
            assert connection_manager.current_http_provider == healthy_provider
            assert connection_manager.failover_count == 1
    
    @pytest.mark.asyncio
    async def test_get_connection_context_manager(self, connection_manager):
        """Test get_connection context manager."""
        # Setup mock connection
        mock_web3 = Mock()
        connection_manager.web3_instance = mock_web3
        connection_manager.current_http_provider = Mock()
        connection_manager.current_http_provider.health.is_available.return_value = True
        
        async with connection_manager.get_connection() as web3:
            assert web3 == mock_web3
            assert connection_manager.total_requests == 1
    
    @pytest.mark.asyncio
    async def test_get_connection_no_healthy_connection(self, connection_manager):
        """Test get_connection when no healthy connection available."""
        # No healthy connections
        connection_manager.current_http_provider = None
        
        with patch.object(connection_manager, '_connect_http', return_value=False):
            with pytest.raises(ConnectionError, match="No healthy connections available"):
                async with connection_manager.get_connection():
                    pass
    
    def test_connection_properties(self, connection_manager):
        """Test connection status properties."""
        # Initially not connected
        assert not connection_manager.is_connected
        assert not connection_manager.is_websocket_connected
        
        # Setup HTTP connection
        from rofl_paymaster.connection import ProviderInfo, ProviderHealth, ConnectionStatus
        
        http_provider = ProviderInfo(url="https://test.example.com")
        http_provider.health.status = ConnectionStatus.HEALTHY
        connection_manager.current_http_provider = http_provider
        connection_manager.web3_instance = Mock()
        
        assert connection_manager.is_connected
        
        # Setup WebSocket connection
        ws_provider = ProviderInfo(url="wss://test.example.com", is_websocket=True)
        ws_provider.health.status = ConnectionStatus.HEALTHY
        connection_manager.current_ws_provider = ws_provider
        
        assert connection_manager.is_websocket_connected
    
    def test_get_connection_stats(self, connection_manager):
        """Test connection statistics."""
        # Setup some state
        connection_manager.total_requests = 100
        connection_manager.failed_requests = 5
        connection_manager.failover_count = 2
        
        from rofl_paymaster.connection import ProviderInfo, ProviderHealth, ConnectionStatus
        
        http_provider = ProviderInfo(url="https://test.example.com")
        http_provider.health.status = ConnectionStatus.HEALTHY
        http_provider.health.response_time = 0.5
        http_provider.health.error_count = 1
        connection_manager.current_http_provider = http_provider
        connection_manager.http_providers = [http_provider]
        
        stats = connection_manager.get_connection_stats()
        
        assert stats["chain_name"] == "test_chain"
        assert stats["total_requests"] == 100
        assert stats["failed_requests"] == 5
        assert stats["failover_count"] == 2
        assert stats["current_http_provider"] == "https://test.example.com"
        assert len(stats["http_providers"]) == 1
        assert stats["http_providers"][0]["status"] == "healthy"


class TestProviderHealth:
    """Test ProviderHealth class."""
    
    def test_provider_health_initialization(self):
        """Test ProviderHealth initialization."""
        from rofl_paymaster.connection import ProviderHealth, ConnectionStatus
        
        health = ProviderHealth()
        
        assert health.status == ConnectionStatus.UNKNOWN
        assert health.last_check == 0.0
        assert health.response_time == 0.0
        assert health.error_count == 0
        assert health.consecutive_failures == 0
        assert health.last_error is None
    
    def test_provider_health_status_methods(self):
        """Test ProviderHealth status checking methods."""
        from rofl_paymaster.connection import ProviderHealth, ConnectionStatus
        
        health = ProviderHealth()
        
        # Unknown status
        assert not health.is_healthy()
        assert not health.is_available()
        
        # Healthy status
        health.status = ConnectionStatus.HEALTHY
        assert health.is_healthy()
        assert health.is_available()
        
        # Degraded status
        health.status = ConnectionStatus.DEGRADED
        assert not health.is_healthy()
        assert health.is_available()
        
        # Failed status
        health.status = ConnectionStatus.FAILED
        assert not health.is_healthy()
        assert not health.is_available()


class TestProviderInfo:
    """Test ProviderInfo class."""
    
    def test_provider_info_initialization(self):
        """Test ProviderInfo initialization."""
        from rofl_paymaster.connection import ProviderInfo
        
        # HTTP provider
        http_provider = ProviderInfo(url="https://test.example.com")
        assert http_provider.url == "https://test.example.com"
        assert not http_provider.is_websocket
        assert http_provider.provider is None
        assert http_provider.connection_attempts == 0
        
        # WebSocket provider
        ws_provider = ProviderInfo(url="wss://test.example.com")
        assert ws_provider.url == "wss://test.example.com"
        assert ws_provider.is_websocket
    
    def test_provider_info_websocket_detection(self):
        """Test WebSocket URL detection."""
        from rofl_paymaster.connection import ProviderInfo
        
        test_cases = [
            ("https://test.example.com", False),
            ("http://test.example.com", False),
            ("wss://test.example.com", True),
            ("ws://test.example.com", True),
        ]
        
        for url, expected_is_websocket in test_cases:
            provider = ProviderInfo(url=url)
            assert provider.is_websocket == expected_is_websocket