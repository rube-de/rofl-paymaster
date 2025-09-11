# Product Requirements Document: ROFL Cross-Chain Paymaster

## Executive Summary

The ROFL Cross-Chain Paymaster is a Python-based Runtime Off-chain Logic application that enables users to pay with USDC on Base and receive ROSE on Oasis Sapphire. The application serves as a trusted bridge operator and blockhash oracle, monitoring deposits on Base and coordinating cross-chain transfers to Sapphire.

## Product Overview

### Vision
Create a seamless cross-chain payment experience where users can use their existing USDC holdings to pay for gas and acquire tokens on Oasis Sapphire, abstracting away the complexity of bridging and token swaps.

### Core Value Proposition
- **Single-Step Process**: Users deposit USDC on Base and automatically receive ROSE on Sapphire
- **Gas Abstraction**: Pay Sapphire gas fees using USDC without needing ROSE upfront
- **Secure Bridging**: TEE-secured execution environment with cryptographic proof verification
- **Extensible Architecture**: Support for multiple chains and assets in future iterations

## Functional Requirements

### 1. Deposit Monitoring

#### 1.1 Event Detection
- **Requirement**: Monitor `PaymasterDeposit` events from the Base vault contract
- **Acceptance Criteria**:
  - Detect new deposit events within 2 blocks of emission
  - Parse event data correctly (sender, recipient, amount, depositId, message)
  - Handle chain reorganizations gracefully
  - Maintain connection stability with automatic reconnection

#### 1.2 Confirmation Waiting
- **Requirement**: Wait for sufficient block confirmations before processing
- **Acceptance Criteria**:
  - Wait for 12 block confirmations on Base
  - Track confirmation progress
  - Handle edge cases where blocks are reorganized

### 2. Proof Generation

#### 2.1 Merkle Proof Creation
- **Requirement**: Generate cryptographic proofs compatible with ProvethVerifier.sol
- **Acceptance Criteria**:
  - Create valid RLP-encoded block headers
  - Build transaction proof stacks using Merkle Patricia Trie
  - Generate proofs that pass on-chain verification
  - Handle different transaction types (legacy, EIP-1559)

#### 2.2 Data Integrity
- **Requirement**: Ensure proof data matches deposit events exactly
- **Acceptance Criteria**:
  - Verify transaction hash matches
  - Confirm log index is correct
  - Validate event signature matches PaymasterDeposit

### 3. Price Oracle Integration

#### 3.1 Multi-Source Price Fetching
- **Requirement**: Fetch USDC and ROSE prices from multiple sources
- **Acceptance Criteria**:
  - Support CoinGecko and Binance APIs
  - Calculate median price from available sources
  - Handle API failures gracefully with fallbacks
  - Implement 5-minute price caching

#### 3.2 Exchange Rate Calculation
- **Requirement**: Calculate accurate ROSE amounts for USDC deposits
- **Acceptance Criteria**:
  - Apply 0.5% slippage protection
  - Handle decimal conversions correctly (USDC: 6, ROSE: 18)
  - Round down to ensure sufficient ROSE in contract

### 4. Blockhash Oracle Service

#### 4.1 Blockhash Attestation
- **Requirement**: Act as trusted oracle for Base chain blockhashes
- **Acceptance Criteria**:
  - Update blockhashes on Sapphire oracle contract
  - Maintain recent 100 blocks in oracle
  - Sign attestations with ROFL operator key
  - Update at least every 50 blocks

#### 4.2 Oracle Reliability
- **Requirement**: Ensure oracle data is always available for verification
- **Acceptance Criteria**:
  - Monitor oracle contract state
  - Alert on stale blockhash data
  - Implement retry logic for failed updates

### 5. Sapphire Transaction Submission

#### 5.1 Transaction Building
- **Requirement**: Submit valid transactions to Sapphire paymaster contract
- **Acceptance Criteria**:
  - Encode deposit data correctly
  - Include valid proofs in transaction
  - Set appropriate gas limits
  - Handle nonce management

#### 5.2 Transaction Monitoring
- **Requirement**: Track submitted transactions to completion
- **Acceptance Criteria**:
  - Wait for transaction receipts
  - Handle failed transactions with retries
  - Log successful completions
  - Alert on persistent failures

## Non-Functional Requirements

### 1. Performance

#### 1.1 Processing Speed
- Detect deposits within 24 seconds (2 Base blocks)
- Generate proofs in under 5 seconds
- Submit to Sapphire within 10 seconds of confirmation

#### 1.2 Throughput
- Handle at least 100 deposits per hour
- Support batch processing for gas optimization
- Maintain performance under load

### 2. Reliability

#### 2.1 Uptime
- 99.9% uptime for monitoring service
- Automatic recovery from crashes
- Graceful handling of RPC endpoint failures

#### 2.2 Data Consistency
- No duplicate deposit processing
- Accurate proof generation 100% of the time
- Consistent price oracle data

### 3. Security

#### 3.1 Key Management
- Secure storage of ROFL operator private key
- Environment variable based configuration
- No hardcoded secrets in code

#### 3.2 Input Validation
- Validate all external data inputs
- Sanitize event data before processing
- Verify contract addresses match configuration

### 4. Scalability

#### 4.1 Horizontal Scaling
- Support multiple ROFL instances (future)
- Implement deposit claiming mechanism
- Avoid race conditions between operators

#### 4.2 Resource Management
- Efficient memory usage for event processing
- Connection pooling for RPC endpoints
- Proper async/await patterns

## Technical Specifications

### 1. Technology Stack

#### Core Dependencies
- **Python**: >=3.9
- **web3.py**: >=6.0.0 (Ethereum interaction)
- **aiohttp**: >=3.8.0 (Async HTTP client)
- **eth-utils**: >=2.0.0 (Ethereum utilities)
- **rlp**: >=3.0.0 (RLP encoding)
- **eth-abi**: >=4.0.0 (ABI encoding/decoding)

#### Development Tools
- **pytest**: Testing framework
- **black**: Code formatter (88 char line length)
- **mypy**: Type checking
- **Docker**: Containerization

### 2. Architecture

#### 2.1 Main Components
- **CrossChainPaymasterMonitor**: Core monitoring class
- **PriceOracle**: Multi-source price fetching
- **ProofGenerator**: Merkle proof creation
- **BlockhashOracle**: Attestation service

#### 2.2 Configuration
- YAML-based configuration file
- Environment variable support
- Contract ABI management

### 3. Data Models

#### 3.1 DepositEvent
```python
@dataclass
class DepositEvent:
    sender: str
    recipient: str
    asset: str
    amount: int
    deposit_id: bytes
    message: bytes
    block_number: int
    tx_hash: str
    log_index: int
```

#### 3.2 Proof Structure
```python
{
    'rlpBlockHeader': str,
    'blockNumber': int,
    'transactionIndexRlp': str,
    'transactionProofStack': str,
    'logIndex': int,
    'expectedEventSignature': str
}
```

## Integration Requirements

### 1. External Services

#### 1.1 Base Chain RPC
- Mainnet endpoint: https://mainnet.base.org
- WebSocket support for event subscriptions
- Backup RPC endpoints for failover

#### 1.2 Sapphire Chain RPC
- Mainnet endpoint: https://sapphire.oasis.io
- Support for confidential transactions
- Gas price monitoring

#### 1.3 Price APIs
- CoinGecko API (rate limits: 50 calls/minute)
- Binance API (rate limits: 1200 requests/minute)
- Implement rate limiting and caching

### 2. Smart Contract Interfaces

#### 2.1 Base Vault Contract
- Monitor PaymasterDeposit events
- No write operations required

#### 2.2 Sapphire Paymaster Contract
- Call `processDeposit` function
- Requires operator signature

#### 2.3 Blockhash Oracle Contract
- Call `setMultipleBlockHashes` function
- Batch updates for efficiency

## Testing Requirements

### 1. Unit Tests
- Proof generation logic
- Price calculation accuracy
- Event parsing correctness
- Error handling scenarios

### 2. Integration Tests
- End-to-end deposit processing
- RPC connection stability
- Smart contract interactions
- Price oracle failover

### 3. Performance Tests
- Load testing with multiple deposits
- Memory usage profiling
- Connection pool efficiency

## Deployment Requirements

### 1. Environment Setup
- Python 3.9+ runtime
- Access to Base and Sapphire RPC endpoints
- Funded ROFL operator account on Sapphire
- Docker container for production

### 2. Configuration
- Environment variables for sensitive data
- YAML configuration for non-sensitive settings
- Contract addresses and ABIs

### 3. Monitoring
- Application logs with structured format
- Metrics collection (deposits processed, failures, latency)
- Alert configuration for failures

## Success Metrics

### 1. Operational Metrics
- **Deposit Processing Time**: <5 minutes average
- **Success Rate**: >99% of valid deposits
- **Uptime**: >99.9% monthly

### 2. Business Metrics
- **Daily Volume**: Track USDC processed
- **User Count**: Unique addresses served
- **Gas Efficiency**: Cost per transaction

### 3. Technical Metrics
- **Proof Generation Time**: <5 seconds
- **API Response Time**: <1 second
- **Memory Usage**: <500MB steady state

## Future Enhancements

### Phase 2 Features
- Support for additional source chains (Ethereum, Arbitrum)
- Multiple asset types (ETH, USDT)
- Batch deposit processing
- WebSocket-based event monitoring

### Phase 3 Features
- Bidirectional flows (ROSE → USDC)
- Multi-operator support
- Light client integration in TEE
- Zero-knowledge proof integration

## Risk Analysis

### Technical Risks
- **RPC Endpoint Reliability**: Mitigated by multiple endpoints and reconnection logic
- **Proof Generation Complexity**: Extensive testing and validation required
- **Gas Price Volatility**: Dynamic gas pricing with caps

### Operational Risks
- **Price Oracle Manipulation**: Multi-source median calculation
- **Chain Reorganizations**: 12 block confirmation requirement
- **Operator Key Compromise**: Secure key management practices

### Economic Risks
- **ROSE Liquidity**: Monitor contract balance and alert
- **Price Volatility**: 0.5% slippage protection
- **Large Orders**: Implement per-transaction limits

## Acceptance Criteria

The ROFL Cross-Chain Paymaster will be considered complete when:

1. Successfully processes test deposits from Base to Sapphire
2. Generates valid proofs that pass on-chain verification
3. Maintains 99%+ success rate over 1 week of testing
4. Handles all error scenarios gracefully
5. Meets performance requirements under load
6. Passes security review
7. Documentation is complete and accurate