# Web3 Connection Management System

This document describes the comprehensive Web3 connection management system implemented for the ROFL Paymaster, which provides robust, production-ready connectivity to Base L2 and Oasis Sapphire chains.

## Overview

The connection management system consists of several key components working together to provide:

- **High Availability**: Automatic failover between multiple RPC endpoints
- **Performance**: Connection pooling and intelligent routing 
- **Real-time Monitoring**: WebSocket event subscriptions with reconnection
- **Reliability**: Health checking, circuit breaker patterns, and graceful degradation
- **Observability**: Comprehensive metrics and logging

## Architecture

### Core Components

1. **ConnectionManager** (`connection.py`)
   - Primary connection management with failover logic
   - Health checking and automatic reconnection
   - WebSocket support for event monitoring
   - Metrics collection and reporting

2. **ConnectionPool** (`connection_pool.py`) 
   - Advanced connection pooling for HTTP providers
   - Automatic connection lifecycle management
   - Configurable pool sizing and cleanup policies
   - Performance optimization through connection reuse

3. **WebSocketManager** (`websocket_manager.py`)
   - Dedicated WebSocket connection management
   - Event subscription and processing
   - Automatic reconnection with exponential backoff
   - Real-time event monitoring capabilities

4. **Web3Helpers** (`web3_helpers.py`)
   - Utility functions for common Web3 operations
   - Gas estimation with EIP-1559 support
   - Transaction status monitoring
   - Account and address utilities

5. **Web3Integration** (`web3_integration.py`)
   - Unified interface combining all components
   - Dual-chain support (Base + Sapphire)
   - Health monitoring and comprehensive statistics
   - Simplified API for application use

## Usage Examples

### Basic Usage

```python
import asyncio
from rofl_paymaster import create_web3_integration_from_config, load_config

async def main():
    # Load configuration
    config = load_config("config.yaml")
    
    # Create Web3 integration
    web3_integration = await create_web3_integration_from_config(
        base_config=config.base_chain,
        sapphire_config=config.sapphire_chain,
        monitoring_config=config.monitoring,
        enable_connection_pool=True
    )
    
    try:
        # Use Base chain connection
        async with web3_integration.get_base_connection() as base_web3:
            block_number = base_web3.eth.block_number
            print(f"Latest Base block: {block_number}")
        
        # Use Sapphire chain connection  
        async with web3_integration.get_sapphire_connection() as sapphire_web3:
            chain_id = sapphire_web3.eth.chain_id
            print(f"Sapphire chain ID: {chain_id}")
            
    finally:
        await web3_integration.shutdown()

asyncio.run(main())
```

### Event Monitoring

```python
async def event_callback(log_entry):
    print(f"Received event: {log_entry}")

# Subscribe to events
subscription_id = await web3_integration.subscribe_to_base_events(
    contract_address="0x1234...",
    event_signature="0xabcd...",
    callback=event_callback
)

# Later: unsubscribe
await web3_integration.unsubscribe_from_events(subscription_id, "base")
```

### Health Monitoring

```python
# Get comprehensive health status
health = await web3_integration.get_health_status()
print(f"System healthy: {health['overall_healthy']}")

# Get detailed statistics
stats = web3_integration.get_comprehensive_stats()
print(f"Base connections: {stats['base_chain']['connection_manager']['total_requests']}")
```

## Key Features

- **Automatic failover** between multiple RPC endpoints
- **Connection pooling** for improved performance
- **WebSocket event monitoring** with auto-reconnection
- **Comprehensive health checking** and metrics
- **Graceful error handling** and recovery
- **Production-ready** logging and observability

## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_connection.py -v
pytest tests/test_connection_pool.py -v  
pytest tests/test_websocket_manager.py -v
```

## TASK-002 Implementation Status

✅ **COMPLETED**: All subtasks for TASK-002 "Connection Management & Web3 Integration" have been successfully implemented:

- ✅ **TASK-002-1**: ConnectionManager class with failover logic
- ✅ **TASK-002-2**: Connection health checking and reconnection  
- ✅ **TASK-002-3**: Connection pooling for RPC endpoints
- ✅ **TASK-002-4**: WebSocket support for real-time event monitoring
- ✅ **TASK-002-5**: Web3Helper utilities

**Acceptance Criteria Met**:
- ✅ Automatic failover between multiple RPC endpoints
- ✅ WebSocket reconnection on connection drops
- ✅ Connection health monitoring with alerts
- ✅ Connection pool efficiency under load

**Testing Requirements Fulfilled**:
- ✅ Integration tests with RPC endpoint failures and reconnection scenarios
- ✅ Comprehensive test coverage for all components
- ✅ Error handling and recovery validation