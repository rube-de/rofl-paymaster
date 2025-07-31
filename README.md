# ROFL Paymaster

A monorepo containing smart contracts and Oasis ROFL application for paymaster functionality.

## Structure

```
├── contracts/          # Smart contracts (Hardhat)
├── rofl/              # Oasis ROFL Python application
├── Makefile           # Build and development commands
└── README.md          # This file
```

## Quick Start

```bash
# View all available commands
make help

# Install dependencies
make install

# Build everything
make build

# Run tests
make test
```

## Contracts

Smart contracts for the paymaster system.

```bash
# Initialize Hardhat (first time only)
cd contracts && npx hardhat init

# Install dependencies
make contracts-install

# Compile contracts
make contracts-build

# Run tests
make contracts-test

# Deploy
make contracts-deploy
```

## ROFL Application

Python application running on Oasis ROFL runtime.

```bash
# Install dependencies
make rofl-install

# Development mode
make rofl-dev

# Build Docker image
make rofl-build

# Run with Docker
make rofl-run

# Run tests
make rofl-test
```

## Development

1. **Setup Contracts**: `cd contracts && npx hardhat init`
2. **Install Dependencies**: `make install`
3. **Start Development**: `make dev`