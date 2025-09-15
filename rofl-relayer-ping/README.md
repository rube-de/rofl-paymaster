# ROFL Relayer

Automated cross-chain message relay service that monitors Ping events on Ethereum and relays them to Oasis Sapphire using cryptographic proofs.

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
| `SOURCE_RPC_URL` | Yes | Ethereum RPC endpoint (WebSocket or HTTP) |
| `PING_SENDER_ADDRESS` | Yes | PingSender contract address on source chain |
| `PING_RECEIVER_ADDRESS` | Yes | PingReceiver contract address on target chain |
| `ROFL_ADAPTER_ADDRESS` | Yes | ROFLAdapter contract for HashStored events |
| `TARGET_NETWORK` | No | Target network (default: `sapphire-testnet`) |
| `PRIVATE_KEY` | Local only | Private key for signing transactions |

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

# Run locally
SOURCE_RPC_URL=wss://ethereum-sepolia-rpc.publicnode.com \
PING_SENDER_ADDRESS=0x... \
PING_RECEIVER_ADDRESS=0x... \
ROFL_ADAPTER_ADDRESS=0x... \
PRIVATE_KEY=0x... \
uv run python main.py --local
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
main.py                      # Minimal CLI entry point
src/rofl_relayer/
  config.py                  # Configuration management
  relayer.py                 # Main relayer service
  utils/                     # Utility modules
    contract_utility.py      # Contract interactions
    event_listener_utility.py # WebSocket event monitoring
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