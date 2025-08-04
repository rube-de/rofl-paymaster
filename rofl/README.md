# ROFL Cross-Chain Paymaster

An Oasis ROFL (Runtime Off-chain Logic) application that enables cross-chain deposits from Base L2 to Oasis Sapphire. Users deposit USDC on Base and receive ROSE on Sapphire through cryptographic proof verification.

## 🚀 Quick Start

### Prerequisites
- Python 3.9+ with pip
- Git

### 1. Setup Development Environment

```bash
# Clone and navigate to project
cd /path/to/rofl-paymaster/rofl

# Install with development dependencies
pip install -e ".[dev]"
```

### 2. Configuration Setup

```bash
# Generate sample configuration files
python -m rofl_paymaster create-config

# Copy and customize configuration
cp config.yaml.sample config.yaml
cp .env.example .env

# Edit .env with your contract addresses and private keys
# Edit config.yaml to customize RPC endpoints and settings
```

### 3. Run Application

```bash
# Start the paymaster application
python -m rofl_paymaster
```

## 🔧 Development

### Development Commands

```bash
# Run all tests (27 tests)
python -m pytest tests/ -v

# Format code (88 character line length)
python -m black src/ tests/

# Type checking
python -m mypy src/

# Lint code
python -m flake8 src/ tests/
```

### Creating Configuration Files

```bash
# Generate sample config files
python -m rofl_paymaster create-config
```

This creates:
- `config.yaml.sample`: Application configuration template
- `.env.example`: Environment variables template

## 🏗️ Architecture

### Core Components
- **Configuration Management**: YAML-based config with Pydantic validation
- **Environment Management**: Secure handling of private keys and secrets  
- **Structured Logging**: JSON logging with correlation IDs and performance metrics
- **Web3 Integration**: Multi-chain support for Base L2 and Oasis Sapphire

### Key Features
- ✅ **Multi-chain RPC Management**: Failover support for Base and Sapphire
- ✅ **Security**: Private key validation, encryption, audit logging
- ✅ **Configuration**: Environment variable substitution in YAML
- ✅ **Monitoring**: Structured JSON logging with performance timing
- ⏳ **Deposit Monitoring**: Base chain event tracking (TASK-002)
- ⏳ **Proof Generation**: Cryptographic cross-chain verification (TASK-003)
- ⏳ **Price Oracle**: Real-time USDC/ROSE exchange rates (TASK-004)

## 🐳 Docker Deployment

```bash
# Build container image
docker build -t rofl-paymaster .

# Run with environment file
docker run -p 8000:8000 --env-file .env rofl-paymaster
```

## 📁 Project Structure

```
rofl/
├── src/rofl_paymaster/           # Main application code
│   ├── __init__.py              # Package initialization
│   ├── __main__.py              # Application entry point
│   ├── config.py                # Configuration management
│   ├── env.py                   # Environment variable handling
│   └── logging.py               # Structured logging framework
├── tests/                       # Comprehensive test suite
│   ├── test_config.py          # Configuration tests
│   ├── test_env.py             # Environment management tests
│   └── test_logging.py         # Logging framework tests
├── docs/                        # Documentation
│   └── tasks.md                # Implementation task breakdown
├── pyproject.toml              # Python project configuration
├── Dockerfile                  # Container configuration  
├── config.yaml.sample         # Sample application config
├── .env.example               # Sample environment variables
└── README.md                  # This file
```

## 🔐 Environment Variables

Key environment variables (see `.env.example` for complete list):

```bash
# Contract Addresses (Required)
BASE_VAULT_CONTRACT_ADDRESS=0x...
SAPPHIRE_PAYMASTER_CONTRACT_ADDRESS=0x...
BLOCKHASH_ORACLE_CONTRACT_ADDRESS=0x...
PRICE_ORACLE_CONTRACT_ADDRESS=0x...

# Private Key (Required)
PAYMASTER_PRIVATE_KEY=0x...

# Optional Configuration
PAYMASTER_CONFIG_PATH=config.yaml
PAYMASTER_LOG_LEVEL=INFO
PAYMASTER_API_PORT=8000
```

## 📋 Implementation Status

### ✅ Completed Tasks
- **TASK-001**: Project Setup & Configuration (8h)
  - Development environment setup
  - YAML configuration system with validation
  - Environment variable management  
  - Structured JSON logging framework
  - Development tools (black, mypy, pytest, flake8)

### 🔄 Next Tasks
- **TASK-002**: Connection Management & Web3 Integration
- **TASK-003**: Base Chain Deposit Monitoring  
- **TASK-004**: Price Oracle Integration
- **TASK-005**: Proof Generation System

See `docs/tasks.md` for the complete implementation roadmap.

## 🧪 Testing

```bash
# Run full test suite
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_config.py -v

# Run with coverage
python -m pytest tests/ --cov=src/rofl_paymaster
```

Test coverage includes:
- Configuration loading and validation
- Environment variable management
- Structured logging functionality
- Error handling and edge cases

## 🔗 Related Projects

This ROFL paymaster is part of the Oasis bridge ecosystem:
- **Smart Contracts**: `../contracts/` - Solidity contracts for Base and Sapphire
- **Documentation**: Cross-chain bridge design and specifications

## 📄 License

See the main project license for details.