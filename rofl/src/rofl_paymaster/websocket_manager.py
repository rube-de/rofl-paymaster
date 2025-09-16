"""WebSocket manager for real-time event monitoring."""

import asyncio
import json
import time
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid

from web3 import Web3
from web3.providers import WebSocketProvider
from web3.exceptions import Web3Exception
from web3.types import FilterParams, LogReceipt

from .config import Web3Config, MonitoringConfig
from .logging import get_logger


class WebSocketStatus(Enum):
    """WebSocket connection status."""
    
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class EventSubscription:
    """Event subscription information."""
    
    subscription_id: str
    contract_address: str
    event_signature: str
    callback: Callable[[LogReceipt], None]
    filter_params: Optional[FilterParams] = None
    created_at: float = field(default_factory=time.time)
    event_count: int = 0
    last_event: Optional[float] = None
    is_active: bool = True


@dataclass
class WebSocketMetrics:
    """WebSocket connection metrics."""
    
    connection_attempts: int = 0
    successful_connections: int = 0
    disconnections: int = 0
    reconnection_attempts: int = 0
    messages_received: int = 0
    messages_sent: int = 0
    events_processed: int = 0
    errors: int = 0
    uptime_start: Optional[float] = None
    last_disconnect: Optional[float] = None
    
    def get_uptime(self) -> float:
        """Get current uptime in seconds."""
        if self.uptime_start is None:
            return 0.0
        return time.time() - self.uptime_start
    
    def get_connection_rate(self) -> float:
        """Get successful connection rate."""
        if self.connection_attempts == 0:
            return 0.0
        return self.successful_connections / self.connection_attempts


class WebSocketManager:
    """Manages WebSocket connections for real-time event monitoring."""
    
    def __init__(
        self, 
        config: Web3Config, 
        monitoring_config: MonitoringConfig,
        chain_name: str = "unknown"
    ):
        """Initialize WebSocket manager.
        
        Args:
            config: Web3 configuration
            monitoring_config: Monitoring configuration
            chain_name: Name of the chain for logging
        """
        self.config = config
        self.monitoring_config = monitoring_config
        self.chain_name = chain_name
        self.logger = get_logger(f"websocket.{chain_name}")
        
        # Connection management
        self.provider: Optional[WebSocketProvider] = None
        self.web3: Optional[Web3] = None
        self.status = WebSocketStatus.DISCONNECTED
        self.current_url: Optional[str] = None
        self.provider_index = 0
        
        # Subscriptions
        self.subscriptions: Dict[str, EventSubscription] = {}
        self.active_filters: Dict[str, str] = {}  # subscription_id -> filter_id
        
        # Reconnection logic
        self._reconnect_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._max_reconnect_attempts = 5
        self._reconnect_delay = self.monitoring_config.reconnect_delay
        self._heartbeat_interval = 30.0  # seconds
        
        # Event processing
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._event_processor_task: Optional[asyncio.Task] = None
        self._message_handlers: Dict[str, Callable] = {}
        
        # Metrics
        self.metrics = WebSocketMetrics()
        
        # Connection lock
        self._connection_lock = asyncio.Lock()
        
        # Setup message handlers
        self._setup_message_handlers()
    
    def _setup_message_handlers(self) -> None:
        """Setup WebSocket message handlers."""
        self._message_handlers = {
            "eth_subscription": self._handle_subscription_message,
            "error": self._handle_error_message,
        }
    
    async def initialize(self) -> bool:
        """Initialize WebSocket connection."""
        self.logger.info(f"Initializing WebSocket manager for {self.chain_name}")
        
        if not self.config.websocket_urls:
            self.logger.warning("No WebSocket URLs configured")
            return False
        
        # Start event processor
        self._event_processor_task = asyncio.create_task(self._event_processor_loop())
        
        # Connect to WebSocket
        success = await self.connect()
        
        if success:
            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self.logger.info(f"WebSocket manager initialized for {self.chain_name}")
        
        return success
    
    async def shutdown(self) -> None:
        """Shutdown WebSocket manager."""
        self.logger.info(f"Shutting down WebSocket manager for {self.chain_name}")
        
        # Cancel tasks
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                if hasattr(self._reconnect_task, '__await__'):
                    await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                if hasattr(self._heartbeat_task, '__await__'):
                    await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._event_processor_task:
            self._event_processor_task.cancel()
            try:
                if hasattr(self._event_processor_task, '__await__'):
                    await self._event_processor_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect
        await self.disconnect()
        
        self.logger.info(f"WebSocket manager shut down for {self.chain_name}")
    
    async def connect(self) -> bool:
        """Connect to WebSocket provider with failover."""
        async with self._connection_lock:
            if self.status == WebSocketStatus.CONNECTED:
                return True
            
            self.status = WebSocketStatus.CONNECTING
            self.metrics.connection_attempts += 1
            
            # Try each WebSocket URL
            for i, url in enumerate(self.config.websocket_urls):
                try:
                    self.logger.debug(f"Attempting WebSocket connection to {url}")
                    
                    # Create provider
                    provider = WebSocketProvider(url)
                    web3 = Web3(provider)
                    
                    # Test connection
                    await asyncio.wait_for(
                        self._test_websocket_connection(web3),
                        timeout=self.config.timeout
                    )
                    
                    # Connection successful
                    self.provider = provider
                    self.web3 = web3
                    self.current_url = url
                    self.provider_index = i
                    self.status = WebSocketStatus.CONNECTED
                    self.metrics.successful_connections += 1
                    self.metrics.uptime_start = time.time()
                    
                    self.logger.info(f"Connected to WebSocket: {url}")
                    
                    # Restore subscriptions
                    await self._restore_subscriptions()
                    
                    return True
                    
                except Exception as e:
                    self.logger.warning(f"WebSocket connection failed for {url}: {e}")
                    continue
            
            # All connections failed
            self.status = WebSocketStatus.FAILED
            self.logger.error("Failed to connect to any WebSocket provider")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket provider."""
        async with self._connection_lock:
            if self.status == WebSocketStatus.DISCONNECTED:
                return
            
            self.logger.debug("Disconnecting WebSocket")
            
            # Clear subscriptions
            self.active_filters.clear()
            
            # Disconnect provider
            if self.provider:
                try:
                    await self.provider.disconnect()
                except Exception as e:
                    self.logger.error(f"Error disconnecting WebSocket: {e}")
            
            self.provider = None
            self.web3 = None
            self.current_url = None
            self.status = WebSocketStatus.DISCONNECTED
            self.metrics.disconnections += 1
            self.metrics.last_disconnect = time.time()
            self.metrics.uptime_start = None
            
            self.logger.debug("WebSocket disconnected")
    
    async def _test_websocket_connection(self, web3: Web3) -> None:
        """Test WebSocket connection."""
        # Test by getting chain ID
        chain_id = web3.eth.chain_id
        if chain_id != self.config.chain_id:
            raise ValueError(f"Chain ID mismatch: expected {self.config.chain_id}, got {chain_id}")
    
    async def subscribe_to_events(
        self,
        contract_address: str,
        event_signature: str,
        callback: Callable[[LogReceipt], None],
        filter_params: Optional[FilterParams] = None
    ) -> str:
        """Subscribe to contract events.
        
        Args:
            contract_address: Contract address to monitor
            event_signature: Event signature hash
            callback: Callback function for events
            filter_params: Optional filter parameters
            
        Returns:
            Subscription ID
            
        Raises:
            ConnectionError: If not connected to WebSocket
        """
        if self.status != WebSocketStatus.CONNECTED:
            raise ConnectionError("WebSocket not connected")
        
        subscription_id = str(uuid.uuid4())
        
        # Create subscription
        subscription = EventSubscription(
            subscription_id=subscription_id,
            contract_address=contract_address.lower(),
            event_signature=event_signature,
            callback=callback,
            filter_params=filter_params
        )
        
        # Create filter
        filter_params = filter_params or {}
        filter_params.update({
            "address": contract_address,
            "topics": [event_signature]
        })
        
        try:
            # Create log filter subscription
            filter_id = await self.web3.eth.filter(filter_params)
            
            self.subscriptions[subscription_id] = subscription
            self.active_filters[subscription_id] = filter_id
            
            self.logger.info(
                f"Subscribed to events: contract={contract_address}, "
                f"event={event_signature}, subscription_id={subscription_id}"
            )
            
            return subscription_id
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to events: {e}")
            raise
    
    async def unsubscribe_from_events(self, subscription_id: str) -> bool:
        """Unsubscribe from events.
        
        Args:
            subscription_id: Subscription ID to cancel
            
        Returns:
            True if successfully unsubscribed
        """
        if subscription_id not in self.subscriptions:
            return False
        
        try:
            # Remove filter
            if subscription_id in self.active_filters:
                filter_id = self.active_filters[subscription_id]
                await self.web3.eth.uninstall_filter(filter_id)
                del self.active_filters[subscription_id]
            
            # Remove subscription
            subscription = self.subscriptions[subscription_id]
            subscription.is_active = False
            del self.subscriptions[subscription_id]
            
            self.logger.info(f"Unsubscribed from events: {subscription_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe from events: {e}")
            return False
    
    async def _restore_subscriptions(self) -> None:
        """Restore subscriptions after reconnection."""
        if not self.subscriptions:
            return
        
        self.logger.debug(f"Restoring {len(self.subscriptions)} subscriptions")
        
        # Clear old filters
        self.active_filters.clear()
        
        for subscription_id, subscription in list(self.subscriptions.items()):
            if not subscription.is_active:
                continue
            
            try:
                # Recreate filter
                filter_params = subscription.filter_params or {}
                filter_params.update({
                    "address": subscription.contract_address,
                    "topics": [subscription.event_signature]
                })
                
                filter_id = await self.web3.eth.filter(filter_params)
                self.active_filters[subscription_id] = filter_id
                
                self.logger.debug(f"Restored subscription: {subscription_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to restore subscription {subscription_id}: {e}")
                # Mark subscription as inactive
                subscription.is_active = False
    
    async def _event_processor_loop(self) -> None:
        """Background event processing loop."""
        while True:
            try:
                # Check for new events in all active filters
                if self.status == WebSocketStatus.CONNECTED and self.web3:
                    await self._poll_events()
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Event processor error: {e}")
                await asyncio.sleep(1.0)
    
    async def _poll_events(self) -> None:
        """Poll for new events from all active filters."""
        for subscription_id, filter_id in list(self.active_filters.items()):
            if subscription_id not in self.subscriptions:
                continue
            
            subscription = self.subscriptions[subscription_id]
            if not subscription.is_active:
                continue
            
            try:
                # Get new entries
                entries = await self.web3.eth.get_filter_changes(filter_id)
                
                for entry in entries:
                    # Process event
                    await self._process_event(subscription, entry)
                    
            except Exception as e:
                self.logger.error(f"Error polling events for {subscription_id}: {e}")
                # Mark subscription as inactive on repeated errors
                if subscription.last_event and time.time() - subscription.last_event > 300:
                    subscription.is_active = False
    
    async def _process_event(self, subscription: EventSubscription, log_entry: LogReceipt) -> None:
        """Process a single event."""
        try:
            # Update subscription metrics
            subscription.event_count += 1
            subscription.last_event = time.time()
            self.metrics.events_processed += 1
            
            # Call callback
            await asyncio.get_event_loop().run_in_executor(
                None, subscription.callback, log_entry
            )
            
            self.logger.debug(
                f"Processed event: subscription={subscription.subscription_id}, "
                f"block={log_entry.get('blockNumber')}, "
                f"tx={log_entry.get('transactionHash').hex() if log_entry.get('transactionHash') else 'None'}"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing event: {e}")
            self.metrics.errors += 1
    
    def _handle_subscription_message(self, message: Dict[str, Any]) -> None:
        """Handle subscription message."""
        self.metrics.messages_received += 1
        # Handle subscription-specific messages if needed
    
    def _handle_error_message(self, message: Dict[str, Any]) -> None:
        """Handle error message."""
        self.metrics.errors += 1
        self.logger.error(f"WebSocket error message: {message}")
    
    async def _heartbeat_loop(self) -> None:
        """Background heartbeat loop."""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                
                if self.status == WebSocketStatus.CONNECTED:
                    # Send ping or check connection health
                    try:
                        await asyncio.wait_for(
                            self.web3.eth.block_number,
                            timeout=10.0
                        )
                    except Exception as e:
                        self.logger.warning(f"Heartbeat failed: {e}")
                        await self._handle_connection_loss()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat loop error: {e}")
    
    async def _handle_connection_loss(self) -> None:
        """Handle connection loss and attempt reconnection."""
        if self.status in (WebSocketStatus.RECONNECTING, WebSocketStatus.CONNECTING):
            return  # Already handling reconnection
        
        self.logger.warning("WebSocket connection lost, attempting reconnection")
        self.status = WebSocketStatus.RECONNECTING
        
        # Cancel existing reconnection task
        if self._reconnect_task:
            self._reconnect_task.cancel()
        
        # Start reconnection task
        self._reconnect_task = asyncio.create_task(self._reconnection_loop())
    
    async def _reconnection_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        attempt = 0
        base_delay = self._reconnect_delay
        
        while attempt < self._max_reconnect_attempts:
            try:
                attempt += 1
                self.metrics.reconnection_attempts += 1
                
                self.logger.info(f"Reconnection attempt {attempt}/{self._max_reconnect_attempts}")
                
                # Disconnect first
                await self.disconnect()
                
                # Wait before reconnection
                delay = min(base_delay * (2 ** (attempt - 1)), 300)  # Max 5 minutes
                await asyncio.sleep(delay)
                
                # Try to reconnect
                if await self.connect():
                    self.logger.info("WebSocket reconnection successful")
                    return
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Reconnection attempt {attempt} failed: {e}")
        
        # All reconnection attempts failed
        self.logger.error("All reconnection attempts failed")
        self.status = WebSocketStatus.FAILED
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.status == WebSocketStatus.CONNECTED
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information."""
        return {
            "chain_name": self.chain_name,
            "status": self.status.value,
            "current_url": self.current_url,
            "provider_index": self.provider_index,
            "subscriptions": len(self.subscriptions),
            "active_filters": len(self.active_filters),
            "metrics": {
                "connection_attempts": self.metrics.connection_attempts,
                "successful_connections": self.metrics.successful_connections,
                "disconnections": self.metrics.disconnections,
                "reconnection_attempts": self.metrics.reconnection_attempts,
                "messages_received": self.metrics.messages_received,
                "messages_sent": self.metrics.messages_sent,
                "events_processed": self.metrics.events_processed,
                "errors": self.metrics.errors,
                "uptime": self.metrics.get_uptime(),
                "connection_rate": self.metrics.get_connection_rate(),
            },
            "subscription_details": [
                {
                    "id": sub.subscription_id,
                    "contract": sub.contract_address,
                    "event": sub.event_signature,
                    "event_count": sub.event_count,
                    "last_event": sub.last_event,
                    "is_active": sub.is_active,
                }
                for sub in self.subscriptions.values()
            ]
        }