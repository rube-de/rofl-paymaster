#!/usr/bin/env python3
"""Example script demonstrating Web3 integration usage."""

import asyncio
import logging
from typing import Any

from rofl_paymaster import (
    load_config,
    Web3Integration,
    create_web3_integration_from_config
)


async def main():
    """Main example function."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("example")
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config("config.yaml")
        
        # Create Web3 integration
        logger.info("Creating Web3 integration...")
        web3_integration = await create_web3_integration_from_config(
            base_config=config.base_chain,
            sapphire_config=config.sapphire_chain,
            monitoring_config=config.monitoring,
            enable_connection_pool=True,
            pool_config={
                "min_connections": 1,
                "max_connections": 3,
                "max_connection_age": 1800.0,  # 30 minutes
                "max_idle_time": 300.0,        # 5 minutes
            }
        )
        
        logger.info("Web3 integration created successfully")
        
        # Test Base chain connection
        logger.info("Testing Base chain connection...")
        async with web3_integration.get_base_connection() as base_web3:
            chain_id = base_web3.eth.chain_id
            latest_block = base_web3.eth.block_number
            logger.info(f"Base chain - Chain ID: {chain_id}, Latest block: {latest_block}")
        
        # Test Sapphire chain connection
        logger.info("Testing Sapphire chain connection...")
        async with web3_integration.get_sapphire_connection() as sapphire_web3:
            chain_id = sapphire_web3.eth.chain_id
            latest_block = sapphire_web3.eth.block_number
            logger.info(f"Sapphire chain - Chain ID: {chain_id}, Latest block: {latest_block}")
        
        # Test helper functions
        if web3_integration.base:
            logger.info("Testing Base chain helpers...")
            balance = await web3_integration.base.get_balance(
                "0x0000000000000000000000000000000000000000"  # Zero address
            )
            logger.info(f"Zero address balance on Base: {balance} Wei")
        
        if web3_integration.sapphire:
            logger.info("Testing Sapphire chain helpers...")
            balance = await web3_integration.sapphire.get_balance(
                "0x0000000000000000000000000000000000000000"  # Zero address
            )
            logger.info(f"Zero address balance on Sapphire: {balance} Wei")
        
        # Example event subscription (if WebSocket available)
        if web3_integration.is_base_websocket_connected:
            logger.info("Testing Base chain event subscription...")
            
            def event_callback(log_entry: Any) -> None:
                logger.info(f"Received Base event: {log_entry}")
            
            # Subscribe to all events from a contract
            subscription_id = await web3_integration.subscribe_to_base_events(
                contract_address=config.vault_contract.address,
                event_signature="0x" + "0" * 64,  # Example event signature
                callback=event_callback
            )
            
            logger.info(f"Subscribed to Base events: {subscription_id}")
            
            # Wait a bit for potential events
            await asyncio.sleep(5.0)
            
            # Unsubscribe
            await web3_integration.unsubscribe_from_events(subscription_id, "base")
            logger.info("Unsubscribed from Base events")
        
        # Get comprehensive health status
        logger.info("Getting health status...")
        health_status = await web3_integration.get_health_status()
        logger.info(f"Overall healthy: {health_status['overall_healthy']}")
        logger.info(f"Base connected: {web3_integration.is_base_connected}")
        logger.info(f"Sapphire connected: {web3_integration.is_sapphire_connected}")
        logger.info(f"Fully connected: {web3_integration.is_fully_connected}")
        
        # Get comprehensive statistics
        logger.info("Getting comprehensive statistics...")
        stats = web3_integration.get_comprehensive_stats()
        
        # Display connection stats
        if "connection_manager" in stats["base_chain"]:
            base_stats = stats["base_chain"]["connection_manager"]
            logger.info(f"Base connection stats: {base_stats['total_requests']} requests, "
                       f"{base_stats['failed_requests']} failures, "
                       f"{base_stats['failover_count']} failovers")
        
        if "connection_pool" in stats["base_chain"]:
            pool_stats = stats["base_chain"]["connection_pool"]
            logger.info(f"Base pool stats: {pool_stats['total_connections']} connections, "
                       f"{pool_stats['hit_rate']:.2%} hit rate")
        
        logger.info("Example completed successfully")
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise
    
    finally:
        # Always shutdown gracefully
        if 'web3_integration' in locals():
            logger.info("Shutting down Web3 integration...")
            await web3_integration.shutdown()
            logger.info("Shutdown complete")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())