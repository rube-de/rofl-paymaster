"""Main entry point for ROFL Paymaster application."""

import asyncio
import sys

from .config import load_config, create_sample_config
from .env import env_manager
from .logging import configure_logging_from_config, get_logger


async def main():
    """Main application entry point."""
    # Initialize logging with basic configuration first
    logger = get_logger(__name__)

    try:
        # Validate environment variables
        logger.info("Validating environment variables...")
        validation_result = env_manager.validate_environment()
        logger.info(
            "Environment validation completed",
            extra={
                "missing_vars": len(validation_result.get("missing_required", [])),
                "invalid_vars": len(validation_result.get("invalid_values", [])),
                "warnings": len(validation_result.get("warnings", [])),
            },
        )

        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()
        logger.info(
            "Configuration loaded successfully",
            extra={
                "config_file": env_manager.get_env(
                    "PAYMASTER_CONFIG_PATH", "config.yaml"
                ),
                "debug_mode": config.debug,
            },
        )

        # Reconfigure logging with settings from config
        configure_logging_from_config(config.logging.dict())
        logger = get_logger(__name__)  # Get new logger with updated configuration

        logger.info(
            "ROFL Paymaster starting...",
            extra={
                "version": config.version,
                "service": config.app_name,
                "debug": config.debug,
            },
        )

        # Log configuration summary (without sensitive data)
        logger.info(
            "Configuration summary",
            extra={
                "base_chain_id": config.base_chain.chain_id,
                "sapphire_chain_id": config.sapphire_chain.chain_id,
                "vault_contract": config.vault_contract.address,
                "paymaster_contract": config.paymaster_contract.address,
                "confirmation_blocks": config.monitoring.confirmation_blocks,
                "price_cache_ttl": config.price_oracle.cache_ttl,
            },
        )

        # Verify private key access (without logging the actual key)
        try:
            account = env_manager.get_account()
            logger.info(
                "Private key validation successful",
                extra={"paymaster_address": account.address},
            )
        except Exception as e:
            logger.error("Private key validation failed", extra={"error": str(e)})
            sys.exit(1)

        logger.info("ROFL Paymaster initialization completed successfully")

        # TODO: Start the actual paymaster services here
        # For now, just keep the application running
        logger.info("Application is running. Press Ctrl+C to stop.")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown signal received, stopping application...")

    except FileNotFoundError as e:
        logger.error("Configuration file not found", extra={"error": str(e)})
        logger.info("To create a sample configuration file, run:")
        logger.info(
            'python -c "from rofl_paymaster.config import '
            'create_sample_config; create_sample_config()"'
        )
        sys.exit(1)
    except ValueError as e:
        logger.error("Configuration validation failed", extra={"error": str(e)})
        sys.exit(1)
    except Exception as e:
        logger.critical(
            "Unexpected error during startup", extra={"error": str(e)}, exc_info=True
        )
        sys.exit(1)


def create_config_files():
    """Create sample configuration files."""
    try:
        # Create sample config
        create_sample_config()

        # Create sample environment file
        env_manager.create_env_file()

        print("\nSample configuration files created:")
        print("- config.yaml.sample: Application configuration template")
        print("- .env.example: Environment variables template")
        print("\nNext steps:")
        print("1. Copy config.yaml.sample to config.yaml")
        print("2. Copy .env.example to .env")
        print("3. Fill in the required values in both files")
        print("4. Run the application with: python -m rofl_paymaster")

    except Exception as e:
        print(f"Error creating configuration files: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Check if we should create sample config files
    if len(sys.argv) > 1 and sys.argv[1] == "create-config":
        create_config_files()
    else:
        # Run the main application
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\nApplication stopped by user.")
            sys.exit(0)
        except Exception as e:
            print(f"Fatal error: {e}")
            sys.exit(1)
