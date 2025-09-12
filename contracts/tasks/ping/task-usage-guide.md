# Cross-Chain Ping Task Usage Guide

Simple guide for using the cross-chain ping tasks to send messages between chains using Hashi's cryptographic verification.

## Task Organization

Tasks are organized into two folders:
- **`deploy/`** - Contract deployment tasks
- **`ping/`** - Cross-chain messaging operations

## Prerequisites

- Node.js 18+ and Bun runtime  
- Funded accounts on source and destination chains
- Configured networks in `hardhat.config.ts`

## Quick Decision: Production vs Mock

**Use Production ShoyuBashi** (`0x35b6fCe2459fd5A741a4a96dbFF5C852f60Ebb8d`) if:
- You want real multi-oracle security
- You can wait 2-10 minutes for oracle consensus

**Use MockShoyuBashi** if:
- You want immediate testing
- You need full control over block hashes

## Step 1: Deploy Contracts

### Source Chain (e.g., Ethereum Sepolia)

```bash
# Deploy BlockHeaderRequester
bun hardhat deploy:block-header-requester --network eth-sepolia

# Deploy PingSender
bun hardhat deploy:ping-sender \
  --network eth-sepolia \
  --block-header-requester 0xBlockHeaderRequesterAddress...
```

### Destination Chain (e.g., Oasis Sapphire Testnet)

**Option A: Production ShoyuBashi**
```bash
# Use existing production ShoyuBashi
bun hardhat deploy:ping-receiver \
  --network oasis-sapphire-testnet \
  --shoyu-bashi 0x35b6fCe2459fd5A741a4a96dbFF5C852f60Ebb8d
```

**Option B: MockShoyuBashi**  
```bash
# Deploy mock for testing
bun hardhat deploy:mock-shoyu-bashi --network oasis-sapphire-testnet

# Deploy PingReceiver with mock
bun hardhat deploy:ping-receiver \
  --network oasis-sapphire-testnet \
  --shoyu-bashi 0xMockShoyuBashiAddress...
```

## Step 2: Send Cross-Chain Ping

```bash
bun hardhat send-ping \
  --network eth-sepolia \
  --sender 0xPingSenderAddress...

# Save the transaction hash and ping ID from output
```

## Step 3: Generate Proof

```bash
bun hardhat generate-proof \
  --network eth-sepolia \
  --tx-hash 0xPingTransactionHash...

# This saves proof.json automatically
```

## Step 4: Setup Oracle (MockShoyuBashi Only)

**Skip this step for Production ShoyuBashi**

```bash
# For MockShoyuBashi only - post block hash manually
bun hardhat post-blockhash \
  --network oasis-sapphire-testnet \
  --contract 0xMockShoyuBashiAddress... \
  --chain-id 11155111 \
  --block-number 4567890 \
  --block-hash 0xBlockHashFromPing...
```

## Step 5: Relay Message

```bash
bun hardhat relay-message \
  --network oasis-sapphire-testnet \
  --receiver 0xPingReceiverAddress... \
  --proof proof.json
```

## Step 6: Verify Success

```bash
bun hardhat check-ping \
  --network oasis-sapphire-testnet \
  --receiver 0xPingReceiverAddress... \
  --ping-id 0xPingIdFromStep2...
```

## Automation Scripts

### Production ShoyuBashi
```bash
# Complete flow - waits for oracle consensus
SOURCE_NETWORK="eth-sepolia"
DEST_NETWORK="oasis-sapphire-testnet"
PING_SENDER="0xPingSender..."
PING_RECEIVER="0xPingReceiver..."

# Send and capture details
PING_RESULT=$(bun hardhat send-ping --network $SOURCE_NETWORK --sender $PING_SENDER)
TX_HASH=$(echo "$PING_RESULT" | grep "Transaction hash:" | cut -d' ' -f3)
PING_ID=$(echo "$PING_RESULT" | grep "Ping ID:" | cut -d' ' -f3)

# Generate proof
bun hardhat generate-proof --network $SOURCE_NETWORK --tx-hash $TX_HASH

# Wait for oracle consensus
sleep 300

# Relay and verify
bun hardhat relay-message --network $DEST_NETWORK --receiver $PING_RECEIVER --proof proof.json
bun hardhat check-ping --network $DEST_NETWORK --receiver $PING_RECEIVER --ping-id $PING_ID
```

### MockShoyuBashi
```bash
# Complete flow - includes manual oracle setup
SOURCE_NETWORK="eth-sepolia"
DEST_NETWORK="oasis-sapphire-testnet"  
PING_SENDER="0xPingSender..."
PING_RECEIVER="0xPingReceiver..."
MOCK_SHOYU_BASHI="0xMockShoyuBashi..."

# Send and capture details
PING_RESULT=$(bun hardhat send-ping --network $SOURCE_NETWORK --sender $PING_SENDER)
TX_HASH=$(echo "$PING_RESULT" | grep "Transaction hash:" | cut -d' ' -f3)
PING_ID=$(echo "$PING_RESULT" | grep "Ping ID:" | cut -d' ' -f3)
BLOCK_NUMBER=$(echo "$PING_RESULT" | grep "Block number:" | cut -d' ' -f3)

# Generate proof  
bun hardhat generate-proof --network $SOURCE_NETWORK --tx-hash $TX_HASH

# Get block hash and setup oracle
BLOCK_HASH=$(bun hardhat run --network $SOURCE_NETWORK -c "console.log((await ethers.provider.getBlock($BLOCK_NUMBER)).hash)")
bun hardhat post-blockhash --network $DEST_NETWORK --contract $MOCK_SHOYU_BASHI --chain-id 11155111 --block-number $BLOCK_NUMBER --block-hash $BLOCK_HASH

# Relay and verify
bun hardhat relay-message --network $DEST_NETWORK --receiver $PING_RECEIVER --proof proof.json  
bun hardhat check-ping --network $DEST_NETWORK --receiver $PING_RECEIVER --ping-id $PING_ID
```

## Common Issues

**"Ping Already Received"** - Each ping can only be relayed once. Send a new ping.

**"Invalid Proof"** - 
- Production: Wait longer for oracle consensus (up to 10 minutes)
- Mock: Ensure you posted the correct block hash

**"Transaction Receipt Not Found"** - Wait for transaction confirmation before generating proof.

**"Contract Not Found"** - Verify contract addresses and network configuration.