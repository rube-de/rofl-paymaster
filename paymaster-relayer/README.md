# Paymaster Relayer

Automated relay that watches PaymasterVault `PaymentInitiated` events on the source chain and submits Hashi receipt proofs to `CrossChainPaymaster` on Oasis Sapphire.

## Quick Start

### Configure Environment

```bash
cp .env.example .env
# Edit .env with your contract addresses and RPC URL
```

### Run with Docker

```bash
# Build image
docker compose build

# Run in ROFL mode (production)
docker compose up

# Run in local mode (development)
docker compose -f compose.local.yaml up
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SOURCE_RPC_URL` | Yes | Source chain RPC endpoint (HTTP) |
| `PAYMASTER_VAULT_ADDRESS` | Yes | PaymasterVault contract address on source chain |
| `TARGET_RPC_URL` | Yes | Sapphire RPC endpoint |
| `PAYMASTER_PROXY_ADDRESS` | Yes | CrossChainPaymaster proxy address on Sapphire |
| `ROFL_ADAPTER_ADDRESS` | Yes | ROFLAdapter on Sapphire to monitor `HashStored` |
| `PRIVATE_KEY` | Local only | Private key for signing transactions (non-ROFL mode) |

## Development

### Local Development

For development with hot reload, uncomment the volume mounts in `compose.local.yaml`:

```yaml
volumes:
  - ./src:/app/src
  - ./main.py:/app/main.py
```

### Running without Docker

```bash
# Install dependencies
uv sync

# Run locally (non-ROFL)
SOURCE_RPC_URL=https://... \
PAYMASTER_VAULT_ADDRESS=0x... \
TARGET_RPC_URL=https://testnet.sapphire.oasis.io \
PAYMASTER_PROXY_ADDRESS=0x... \
PRIVATE_KEY=0x... \
uv run python -m paymaster_relayer --local
```

## Testing

Run the test suite to verify the relayer functionality:

```bash
# Run tests
cd tests
uv run python test_relayer.py
```

The test suite validates:
- PollingEventListener utility class structure
- ROFL Relayer initialization and event monitoring
- Integration with deployed contracts on Ethereum Sepolia

## Architecture

```
paymaster_relayer/
  config.py                  # Configuration management
  relayer.py                 # Main relayer service
  utils/                     # Utility modules
    contract_utility.py      # Contract interactions
    polling_event_listener.py # Polling-based event monitoring
    rofl_utility.py          # ROFL transaction submission
tests/
  test_relayer.py           # Test suite for relayer functionality
```

## Monitoring

```bash
# View logs
docker compose logs -f

# Stop service
docker compose down
```
