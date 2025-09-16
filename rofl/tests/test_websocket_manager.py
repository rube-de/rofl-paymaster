"""Tests for WebSocket manager module."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from web3 import Web3
from web3.exceptions import Web3Exception

from rofl_paymaster.websocket_manager import (
    WebSocketManager, WebSocketStatus, EventSubscription, WebSocketMetrics
)
from rofl_paymaster.config import Web3Config, MonitoringConfig


@pytest.fixture
def mock_web3_config():
    """Mock Web3 configuration."""
    return Web3Config(
        rpc_urls=["https://mainnet.base.org"],
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
def mock_monitoring_config():
    """Mock monitoring configuration."""
    return MonitoringConfig(
        confirmation_blocks=12,
        event_batch_size=1000,
        poll_interval=2.0,
        max_block_range=10000,
        reconnect_delay=5.0,
    )


@pytest.fixture
def websocket_manager(mock_web3_config, mock_monitoring_config):
    """Create WebSocket manager instance."""
    return WebSocketManager(
        config=mock_web3_config,
        monitoring_config=mock_monitoring_config,
        chain_name="test_chain"
    )


class TestEventSubscription:
    """Test EventSubscription class."""
    
    def test_event_subscription_initialization(self):
        """Test EventSubscription initialization."""
        callback = Mock()
        subscription = EventSubscription(
            subscription_id="test-123",
            contract_address="0x1234567890123456789012345678901234567890",
            event_signature="0xabcd1234",
            callback=callback
        )
        
        assert subscription.subscription_id == "test-123"
        assert subscription.contract_address == "0x1234567890123456789012345678901234567890"
        assert subscription.event_signature == "0xabcd1234"
        assert subscription.callback == callback
        assert subscription.filter_params is None
        assert subscription.event_count == 0
        assert subscription.last_event is None
        assert subscription.is_active is True


class TestWebSocketMetrics:
    """Test WebSocketMetrics class."""
    
    def test_websocket_metrics_initialization(self):
        """Test WebSocketMetrics initialization."""
        metrics = WebSocketMetrics()
        
        assert metrics.connection_attempts == 0
        assert metrics.successful_connections == 0
        assert metrics.disconnections == 0
        assert metrics.reconnection_attempts == 0
        assert metrics.messages_received == 0
        assert metrics.messages_sent == 0
        assert metrics.events_processed == 0
        assert metrics.errors == 0
        assert metrics.uptime_start is None
        assert metrics.last_disconnect is None
    
    def test_get_uptime_no_start_time(self):
        """Test get_uptime when no start time set."""
        metrics = WebSocketMetrics()
        assert metrics.get_uptime() == 0.0
    
    def test_get_uptime_with_start_time(self):
        """Test get_uptime with start time set."""
        metrics = WebSocketMetrics()
        start_time = time.time() - 100  # 100 seconds ago
        metrics.uptime_start = start_time
        
        uptime = metrics.get_uptime()
        assert uptime >= 100  # Should be at least 100 seconds
        assert uptime <= 101  # But not much more due to execution time
    
    def test_get_connection_rate_no_attempts(self):
        """Test get_connection_rate with no attempts."""
        metrics = WebSocketMetrics()
        assert metrics.get_connection_rate() == 0.0
    
    def test_get_connection_rate_with_attempts(self):
        """Test get_connection_rate with attempts."""
        metrics = WebSocketMetrics()
        metrics.connection_attempts = 10
        metrics.successful_connections = 8
        
        assert metrics.get_connection_rate() == 0.8


class TestWebSocketManager:
    """Test WebSocketManager class."""
    
    def test_initialization(self, websocket_manager):
        """Test WebSocket manager initialization."""
        assert websocket_manager.chain_name == "test_chain"
        assert websocket_manager.provider is None
        assert websocket_manager.web3 is None
        assert websocket_manager.status == WebSocketStatus.DISCONNECTED
        assert websocket_manager.current_url is None
        assert websocket_manager.provider_index == 0
        assert len(websocket_manager.subscriptions) == 0
        assert len(websocket_manager.active_filters) == 0
        assert isinstance(websocket_manager.metrics, WebSocketMetrics)
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, websocket_manager):
        """Test successful WebSocket manager initialization."""
        with patch.object(websocket_manager, 'connect', return_value=True) as mock_connect:
            result = await websocket_manager.initialize()
            
            assert result is True
            mock_connect.assert_called_once()
            assert websocket_manager._event_processor_task is not None
            assert websocket_manager._heartbeat_task is not None
    
    @pytest.mark.asyncio
    async def test_initialize_no_websocket_urls(self, mock_web3_config, mock_monitoring_config):
        """Test initialization with no WebSocket URLs."""
        mock_web3_config.websocket_urls = None
        manager = WebSocketManager(mock_web3_config, mock_monitoring_config, "test_chain")
        
        result = await manager.initialize()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, websocket_manager):
        """Test initialization with connection failure."""
        with patch.object(websocket_manager, 'connect', return_value=False) as mock_connect:
            result = await websocket_manager.initialize()
            
            assert result is False
            mock_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, websocket_manager):
        """Test WebSocket manager shutdown."""
        # Setup some tasks
        websocket_manager._reconnect_task = Mock()
        websocket_manager._reconnect_task.cancel = Mock()
        websocket_manager._heartbeat_task = Mock()
        websocket_manager._heartbeat_task.cancel = Mock()
        websocket_manager._event_processor_task = Mock()
        websocket_manager._event_processor_task.cancel = Mock()
        
        with patch.object(websocket_manager, 'disconnect') as mock_disconnect:
            await websocket_manager.shutdown()
            
            # Check that all tasks were cancelled
            websocket_manager._reconnect_task.cancel.assert_called_once()
            websocket_manager._heartbeat_task.cancel.assert_called_once()
            websocket_manager._event_processor_task.cancel.assert_called_once()
            mock_disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.websocket_manager.WebSocketProvider')
    @patch('rofl_paymaster.websocket_manager.Web3')
    async def test_connect_success(self, mock_web3, mock_provider, websocket_manager):
        """Test successful WebSocket connection."""
        # Setup mocks
        mock_provider_instance = Mock()
        mock_provider.return_value = mock_provider_instance
        
        mock_web3_instance = Mock()
        mock_web3_instance.eth.chain_id = 8453
        mock_web3.return_value = mock_web3_instance
        
        with patch.object(websocket_manager, '_test_websocket_connection', return_value=None), \
             patch.object(websocket_manager, '_restore_subscriptions') as mock_restore:
            
            result = await websocket_manager.connect()
            
            assert result is True
            assert websocket_manager.status == WebSocketStatus.CONNECTED
            assert websocket_manager.provider == mock_provider_instance
            assert websocket_manager.web3 == mock_web3_instance
            assert websocket_manager.current_url == "wss://mainnet.base.org"
            assert websocket_manager.provider_index == 0
            assert websocket_manager.metrics.successful_connections == 1
            mock_restore.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.websocket_manager.WebSocketProvider')
    @patch('rofl_paymaster.websocket_manager.Web3')
    async def test_connect_failure_with_failover(self, mock_web3, mock_provider, websocket_manager):
        """Test WebSocket connection failure with successful failover."""
        # Setup mocks - first provider fails, second succeeds
        def provider_side_effect(url):
            if "mainnet.base.org" in url:
                raise Web3Exception("Connection failed")
            else:
                return Mock()  # Second provider succeeds
        
        mock_provider.side_effect = provider_side_effect
        
        def web3_side_effect(provider):
            if isinstance(provider, Mock):
                mock_web3_instance = Mock()
                mock_web3_instance.eth.chain_id = 8453
                return mock_web3_instance
            else:
                raise Web3Exception("Connection failed")
        
        mock_web3.side_effect = web3_side_effect
        
        with patch.object(websocket_manager, '_test_websocket_connection', return_value=None), \
             patch.object(websocket_manager, '_restore_subscriptions'):
            
            result = await websocket_manager.connect()
            
            assert result is True
            assert websocket_manager.current_url == "wss://base-mainnet.public.blastapi.io"
            assert websocket_manager.provider_index == 1
    
    @pytest.mark.asyncio
    @patch('rofl_paymaster.websocket_manager.WebSocketProvider')
    @patch('rofl_paymaster.websocket_manager.Web3')
    async def test_connect_all_providers_fail(self, mock_web3, mock_provider, websocket_manager):
        """Test WebSocket connection when all providers fail."""
        # Setup mocks to always fail
        mock_provider.side_effect = Web3Exception("Connection failed")
        
        result = await websocket_manager.connect()
        
        assert result is False
        assert websocket_manager.status == WebSocketStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_disconnect(self, websocket_manager):
        """Test WebSocket disconnection."""
        # Setup connected state
        mock_provider = AsyncMock()
        websocket_manager.provider = mock_provider
        websocket_manager.web3 = Mock()
        websocket_manager.current_url = "wss://test.example.com"
        websocket_manager.status = WebSocketStatus.CONNECTED
        websocket_manager.metrics.uptime_start = time.time()
        
        # Add some active filters
        websocket_manager.active_filters["test-123"] = "filter-456"
        
        await websocket_manager.disconnect()
        
        assert websocket_manager.status == WebSocketStatus.DISCONNECTED
        assert websocket_manager.provider is None
        assert websocket_manager.web3 is None
        assert websocket_manager.current_url is None
        assert len(websocket_manager.active_filters) == 0
        assert websocket_manager.metrics.disconnections == 1
        assert websocket_manager.metrics.last_disconnect is not None
        assert websocket_manager.metrics.uptime_start is None
        
        mock_provider.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_websocket_connection_success(self, websocket_manager):
        """Test WebSocket connection testing success."""
        mock_web3 = AsyncMock()
        mock_web3.eth.chain_id = 8453
        
        # Should not raise exception
        await websocket_manager._test_websocket_connection(mock_web3)
    
    @pytest.mark.asyncio
    async def test_test_websocket_connection_chain_id_mismatch(self, websocket_manager):
        """Test WebSocket connection testing with chain ID mismatch."""
        mock_web3 = AsyncMock()
        mock_web3.eth.chain_id = 1  # Wrong chain ID
        
        with pytest.raises(ValueError, match="Chain ID mismatch"):
            await websocket_manager._test_websocket_connection(mock_web3)
    
    @pytest.mark.asyncio
    async def test_subscribe_to_events_success(self, websocket_manager):
        """Test successful event subscription."""
        # Setup connected state
        websocket_manager.status = WebSocketStatus.CONNECTED
        mock_web3 = AsyncMock()
        mock_web3.eth.filter.return_value = "filter-123"
        websocket_manager.web3 = mock_web3
        
        callback = Mock()
        contract_address = "0x1234567890123456789012345678901234567890"
        event_signature = "0xabcd1234"
        
        subscription_id = await websocket_manager.subscribe_to_events(
            contract_address=contract_address,
            event_signature=event_signature,
            callback=callback
        )
        
        assert subscription_id in websocket_manager.subscriptions
        assert subscription_id in websocket_manager.active_filters
        assert websocket_manager.active_filters[subscription_id] == "filter-123"
        
        subscription = websocket_manager.subscriptions[subscription_id]
        assert subscription.contract_address == contract_address.lower()
        assert subscription.event_signature == event_signature
        assert subscription.callback == callback
        assert subscription.is_active is True
    
    @pytest.mark.asyncio
    async def test_subscribe_to_events_not_connected(self, websocket_manager):
        """Test event subscription when not connected."""
        # Not connected state
        websocket_manager.status = WebSocketStatus.DISCONNECTED
        
        callback = Mock()
        
        with pytest.raises(ConnectionError, match="WebSocket not connected"):
            await websocket_manager.subscribe_to_events(
                contract_address="0x1234567890123456789012345678901234567890",
                event_signature="0xabcd1234",
                callback=callback
            )
    
    @pytest.mark.asyncio
    async def test_unsubscribe_from_events_success(self, websocket_manager):
        """Test successful event unsubscription."""
        # Setup subscription
        callback = Mock()
        subscription = EventSubscription(
            subscription_id="test-123",
            contract_address="0x1234567890123456789012345678901234567890",
            event_signature="0xabcd1234",
            callback=callback
        )
        
        websocket_manager.subscriptions["test-123"] = subscription
        websocket_manager.active_filters["test-123"] = "filter-456"
        
        # Setup connected state
        mock_web3 = AsyncMock()
        websocket_manager.web3 = mock_web3
        
        result = await websocket_manager.unsubscribe_from_events("test-123")
        
        assert result is True
        assert "test-123" not in websocket_manager.subscriptions
        assert "test-123" not in websocket_manager.active_filters
        assert not subscription.is_active
        
        mock_web3.eth.uninstall_filter.assert_called_once_with("filter-456")
    
    @pytest.mark.asyncio
    async def test_unsubscribe_from_events_not_found(self, websocket_manager):
        """Test unsubscribing from non-existent subscription."""
        result = await websocket_manager.unsubscribe_from_events("non-existent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_restore_subscriptions(self, websocket_manager):
        """Test restoring subscriptions after reconnection."""
        # Setup subscription
        callback = Mock()
        subscription = EventSubscription(
            subscription_id="test-123",
            contract_address="0x1234567890123456789012345678901234567890",
            event_signature="0xabcd1234",
            callback=callback
        )
        
        websocket_manager.subscriptions["test-123"] = subscription
        
        # Setup connected state
        mock_web3 = AsyncMock()
        mock_web3.eth.filter.return_value = "new-filter-789"
        websocket_manager.web3 = mock_web3
        
        await websocket_manager._restore_subscriptions()
        
        assert websocket_manager.active_filters["test-123"] == "new-filter-789"
        mock_web3.eth.filter.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_restore_subscriptions_failure(self, websocket_manager):
        """Test restoring subscriptions with failure."""
        # Setup subscription
        callback = Mock()
        subscription = EventSubscription(
            subscription_id="test-123",
            contract_address="0x1234567890123456789012345678901234567890",
            event_signature="0xabcd1234",
            callback=callback
        )
        
        websocket_manager.subscriptions["test-123"] = subscription
        
        # Setup connected state with failing filter creation
        mock_web3 = AsyncMock()
        mock_web3.eth.filter.side_effect = Web3Exception("Filter creation failed")
        websocket_manager.web3 = mock_web3
        
        await websocket_manager._restore_subscriptions()
        
        # Subscription should be marked as inactive
        assert not subscription.is_active
        assert "test-123" not in websocket_manager.active_filters
    
    @pytest.mark.asyncio
    async def test_poll_events(self, websocket_manager):
        """Test polling for events."""
        # Setup subscription and filter
        callback = Mock()
        subscription = EventSubscription(
            subscription_id="test-123",
            contract_address="0x1234567890123456789012345678901234567890",
            event_signature="0xabcd1234",
            callback=callback
        )
        
        websocket_manager.subscriptions["test-123"] = subscription
        websocket_manager.active_filters["test-123"] = "filter-456"
        websocket_manager.status = WebSocketStatus.CONNECTED
        
        # Setup mock Web3 with event data
        mock_log_entry = {
            "blockNumber": 12345,
            "transactionHash": "0xabcdef123456",
            "address": "0x1234567890123456789012345678901234567890",
            "topics": ["0xabcd1234"],
            "data": "0x"
        }
        
        mock_web3 = AsyncMock()
        mock_web3.eth.get_filter_changes.return_value = [mock_log_entry]
        websocket_manager.web3 = mock_web3
        
        with patch.object(websocket_manager, '_process_event') as mock_process:
            await websocket_manager._poll_events()
            
            mock_process.assert_called_once_with(subscription, mock_log_entry)
    
    @pytest.mark.asyncio
    async def test_process_event_success(self, websocket_manager):
        """Test successful event processing."""
        callback = Mock()
        subscription = EventSubscription(
            subscription_id="test-123",
            contract_address="0x1234567890123456789012345678901234567890",
            event_signature="0xabcd1234",
            callback=callback
        )
        
        mock_log_entry = {
            "blockNumber": 12345,
            "transactionHash": "0xabcdef123456",
        }
        
        await websocket_manager._process_event(subscription, mock_log_entry)
        
        assert subscription.event_count == 1
        assert subscription.last_event is not None
        assert websocket_manager.metrics.events_processed == 1
    
    @pytest.mark.asyncio
    async def test_handle_connection_loss(self, websocket_manager):
        """Test handling connection loss."""
        websocket_manager.status = WebSocketStatus.CONNECTED
        
        with patch.object(websocket_manager, '_reconnection_loop') as mock_reconnect:
            await websocket_manager._handle_connection_loss()
            
            assert websocket_manager.status == WebSocketStatus.RECONNECTING
            assert websocket_manager._reconnect_task is not None
    
    def test_is_connected_property(self, websocket_manager):
        """Test is_connected property."""
        # Initially not connected
        assert not websocket_manager.is_connected
        
        # Set to connected
        websocket_manager.status = WebSocketStatus.CONNECTED
        assert websocket_manager.is_connected
        
        # Set to other states
        websocket_manager.status = WebSocketStatus.RECONNECTING
        assert not websocket_manager.is_connected
    
    def test_get_connection_info(self, websocket_manager):
        """Test connection information."""
        # Setup some state
        websocket_manager.status = WebSocketStatus.CONNECTED
        websocket_manager.current_url = "wss://test.example.com"
        websocket_manager.provider_index = 1
        websocket_manager.metrics.connection_attempts = 5
        websocket_manager.metrics.successful_connections = 4
        websocket_manager.metrics.events_processed = 100
        
        # Add a subscription
        callback = Mock()
        subscription = EventSubscription(
            subscription_id="test-123",
            contract_address="0x1234567890123456789012345678901234567890",
            event_signature="0xabcd1234",
            callback=callback
        )
        subscription.event_count = 10
        websocket_manager.subscriptions["test-123"] = subscription
        websocket_manager.active_filters["test-123"] = "filter-456"
        
        info = websocket_manager.get_connection_info()
        
        assert info["chain_name"] == "test_chain"
        assert info["status"] == "connected"
        assert info["current_url"] == "wss://test.example.com"
        assert info["provider_index"] == 1
        assert info["subscriptions"] == 1
        assert info["active_filters"] == 1
        assert info["metrics"]["connection_attempts"] == 5
        assert info["metrics"]["successful_connections"] == 4
        assert info["metrics"]["events_processed"] == 100
        assert info["metrics"]["connection_rate"] == 0.8
        
        # Check subscription details
        assert len(info["subscription_details"]) == 1
        sub_detail = info["subscription_details"][0]
        assert sub_detail["id"] == "test-123"
        assert sub_detail["contract"] == "0x1234567890123456789012345678901234567890"
        assert sub_detail["event"] == "0xabcd1234"
        assert sub_detail["event_count"] == 10
        assert sub_detail["is_active"] is True