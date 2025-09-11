#!/usr/bin/env python3

import argparse
import asyncio
import logging
import sys
from src.rofl_relayer.relayer import ROFLRelayer

# Set up root logger
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for the ROFL Relayer."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="ROFL Relayer")
    parser.add_argument(
        "--local",
        action="store_true",
        default=False,
        help="Run in local mode without ROFL utilities"
    )
    args = parser.parse_args()
    
    logger.info(f"=== ROFL Relayer Starting {'(LOCAL MODE)' if args.local else ''} ===")
    
    relayer = None
    
    try:
        # Create relayer using factory method
        relayer = ROFLRelayer.from_env(local_mode=args.local)
        await relayer.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Required environment variables:")
        logger.error("  - SOURCE_RPC_URL: Source chain RPC endpoint (e.g., Ethereum)")
        logger.error("  - TARGET_RPC_URL: Target chain RPC endpoint (e.g., Sapphire)")
        logger.error("  - PING_SENDER_ADDRESS: PingSender contract address")
        logger.error("  - PING_RECEIVER_ADDRESS: PingReceiver contract address")
        logger.error("  - ROFL_ADAPTER_ADDRESS: ROFLAdapter contract address")
        if args.local:
            logger.error("  - PRIVATE_KEY: Private key for signing transactions")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if relayer is not None:
            logger.debug("Stopping relayer...")
            relayer.stop()


if __name__ == "__main__":
    asyncio.run(main())