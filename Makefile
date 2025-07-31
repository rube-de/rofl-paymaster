.PHONY: help build test clean install dev

# Default target
help:
	@echo "Available commands:"
	@echo "  make install    - Install all dependencies"
	@echo "  make build      - Build all components"
	@echo "  make test       - Run all tests"
	@echo "  make clean      - Clean all build artifacts"
	@echo "  make dev        - Start development environment"
	@echo ""
	@echo "Contract commands:"
	@echo "  make contracts-install  - Install contract dependencies"
	@echo "  make contracts-build    - Compile smart contracts"
	@echo "  make contracts-test     - Run contract tests"
	@echo "  make contracts-deploy   - Deploy contracts"
	@echo ""
	@echo "ROFL commands:"
	@echo "  make rofl-install      - Install ROFL dependencies"
	@echo "  make rofl-build        - Build ROFL Docker image"
	@echo "  make rofl-run          - Run ROFL application"
	@echo "  make rofl-dev          - Start ROFL in development mode"
	@echo "  make rofl-test         - Run ROFL tests"

# Install all dependencies
install: contracts-install rofl-install

# Build all components
build: contracts-build rofl-build

# Test all components
test: contracts-test rofl-test

# Clean all build artifacts
clean: contracts-clean rofl-clean

# Development environment
dev:
	@echo "Starting development environment..."
	@echo "Contracts: Ready for hardhat init"
	@echo "ROFL: Run 'make rofl-dev' to start"

# Contract targets
contracts-install:
	@if [ -f contracts/package.json ]; then \
		cd contracts && npm install; \
	else \
		echo "No package.json found in contracts/ - run 'npx hardhat init' first"; \
	fi

contracts-build:
	@if [ -f contracts/hardhat.config.js ] || [ -f contracts/hardhat.config.ts ]; then \
		cd contracts && npx hardhat compile; \
	else \
		echo "No hardhat config found - run 'npx hardhat init' first"; \
	fi

contracts-test:
	@if [ -f contracts/hardhat.config.js ] || [ -f contracts/hardhat.config.ts ]; then \
		cd contracts && npx hardhat test; \
	else \
		echo "No hardhat config found - run 'npx hardhat init' first"; \
	fi

contracts-deploy:
	@if [ -f contracts/hardhat.config.js ] || [ -f contracts/hardhat.config.ts ]; then \
		cd contracts && npx hardhat run scripts/deploy.js; \
	else \
		echo "No hardhat config found - run 'npx hardhat init' first"; \
	fi

contracts-clean:
	@if [ -d contracts/artifacts ]; then rm -rf contracts/artifacts; fi
	@if [ -d contracts/cache ]; then rm -rf contracts/cache; fi

# ROFL targets
rofl-install:
	cd rofl && pip install -e ".[dev]"

rofl-build:
	cd rofl && docker build -t rofl-paymaster .

rofl-run:
	cd rofl && docker run -p 8000:8000 rofl-paymaster

rofl-dev:
	cd rofl && python -m rofl_paymaster

rofl-test:
	cd rofl && pytest

rofl-clean:
	cd rofl && find . -type d -name "__pycache__" -exec rm -rf {} + || true
	cd rofl && find . -type f -name "*.pyc" -delete || true
	cd rofl && rm -rf .pytest_cache || true
	cd rofl && rm -rf build/ || true
	cd rofl && rm -rf dist/ || true
	cd rofl && rm -rf *.egg-info || true