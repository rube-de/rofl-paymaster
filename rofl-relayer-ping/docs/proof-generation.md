# Proof Generation Implementation

## Overview

The ROFL Relayer now includes cryptographic proof generation capability that enables cross-chain message verification using the Hashi protocol format. This implementation generates proofs that are byte-for-byte identical to the TypeScript reference implementation.

## Architecture

### ProofManager Class

The `ProofManager` class (`src/rofl_relayer/proof_manager.py`) encapsulates all proof generation logic:

- **Single Responsibility**: All proof logic in one cohesive class
- **Mode Support**: Works in both local mode (with private keys) and ROFL mode (using ROFL utilities)
- **TypeScript Compatibility**: Generates proofs identical to the TypeScript implementation

### Key Methods

1. **`generate_proof(tx_hash, log_index)`**
   - Fetches transaction receipt and block data
   - Retrieves all receipts in the block
   - RLP encodes receipts with proper type handling
   - Builds Merkle Patricia Trie
   - Generates proof path for target receipt
   - Returns 8-element Hashi-format proof array

2. **`submit_proof(proof, receiver_address)`**
   - Submits proof to PingReceiver contract
   - Handles both local and ROFL submission modes
   - Returns transaction hash

3. **`process_ping_event(ping_event, receiver_address)`**
   - Complete flow from event to proof submission
   - Combines generation and submission

## Proof Structure

The proof is an 8-element array matching the Hashi protocol format:

```python
proof = [
    chainId,                 # Source chain ID (e.g., 11155111 for Sepolia)
    blockNumber,             # Block containing the event
    encodedBlockHeader,      # RLP-encoded block header
    0,                      # ancestralBlockNumber (MVP: always 0)
    [],                     # ancestralBlockHeaders (MVP: empty)
    merkleProof,            # Array of proof nodes from the trie
    transactionIndex,       # RLP-encoded transaction index
    logIndex                # Event position in logs
]
```

## Technical Details

### RLP Encoding

The implementation handles different transaction types correctly:

- **Legacy (Type 0)**: No type prefix
- **EIP-1559 (Type 2)**: Prefixed with 0x02 byte

Receipt encoding structure:
```python
[status, cumulative_gas, logs_bloom, logs]
```

### Merkle Patricia Trie

- **Key**: RLP-encoded transaction index
- **Value**: RLP-encoded receipt (with type prefix if needed)
- **Verification**: Trie root must match block's `receiptsRoot`

### Block Header Encoding

The block header is RLP-encoded with all required fields:
- Standard fields (parentHash, stateRoot, etc.)
- Post-London fields (baseFeePerGas)
- Post-Shanghai fields (withdrawalsRoot, if present)

## Integration

### Event Processor Integration

The `EventProcessor` now includes proof generation when matching events are found:

```python
# When Ping and HashStored events match:
await self.process_matched_events(ping_event, block_hash)
```

### Configuration

The proof generation uses existing configuration:
- Source chain RPC for fetching blockchain data
- Target chain addresses for proof submission
- ROFL utilities when running in ROFL mode

## Testing

### Unit Tests (`test/test_proof_logic.py`)

Verifies core logic without requiring blockchain access:
- RLP encoding correctness
- Receipt structure for different transaction types
- Proof structure validation

### Integration Test (`test/test_proof_generation.py`)

Full end-to-end test (requires archive node):
- Generates proof for real transaction
- Compares with TypeScript reference proof
- Validates byte-for-byte equality

## Usage

### Local Mode

```bash
# Set environment variables
export SOURCE_RPC_URL="https://ethereum-sepolia.publicnode.com"
export TARGET_RPC_URL="https://testnet.sapphire.oasis.io"
export PING_SENDER_ADDRESS="0x..."
export PING_RECEIVER_ADDRESS="0x..."
export ROFL_ADAPTER_ADDRESS="0x..."
export PRIVATE_KEY="0x..."

# Run relayer
uv run python main.py --local
```

### ROFL Mode

The proof generation automatically uses ROFL utilities when available:
- Transactions are signed and submitted via ROFL runtime
- No private key management required

## Performance Considerations

- **Block Receipt Fetching**: Fetches all receipts in parallel
- **Trie Construction**: Uses efficient hexary trie implementation
- **Caching**: Consider implementing proof caching for repeated requests

## Security Notes

- Proofs are cryptographically secure and verifiable on-chain
- No trust assumptions beyond the source chain RPC
- Multi-oracle validation via Hashi protocol

## Future Enhancements

1. **Proof Caching**: Cache generated proofs to avoid redundant computation
2. **Batch Processing**: Generate multiple proofs in parallel
3. **Ancestral Proofs**: Support for historical block verification
4. **Error Recovery**: Implement retry logic for transient failures
5. **Performance Metrics**: Add timing and success rate tracking