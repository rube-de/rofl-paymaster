# Product Requirements Document: Cross-Chain Paymaster Smart Contracts

## Executive Summary

The Cross-Chain Paymaster Smart Contracts enable trustless bridging of assets between Base and Oasis Sapphire chains. The system consists of a USDC vault on Base that locks user deposits and a paymaster contract on Sapphire that verifies proofs and distributes ROSE tokens. The contracts leverage existing Proveth verification infrastructure for secure cross-chain proof validation.

## Product Overview

### Vision
Create a secure, efficient, and extensible smart contract system that enables users to seamlessly convert USDC on Base to ROSE on Oasis Sapphire, with built-in support for cross-chain message passing and future multi-chain/multi-asset expansion.

### Core Value Proposition
- **Trustless Verification**: Cryptographic proof-based verification using proven ProvethVerifier
- **Native Token Distribution**: Direct ROSE transfers for optimal gas efficiency
- **Message Passing**: Optional cross-chain contract calls with deposited funds
- **Future-Proof Architecture**: Extensible design supporting multiple chains and assets

## Functional Requirements

### 1. Base Chain Components

#### 1.1 Paymaster Vault Contract (`PaymasterVault`)

##### 1.1.1 Asset Management
- **Requirement**: Support configurable asset types with validation
- **Acceptance Criteria**:
  - Maintain registry of supported assets with configuration
  - Enforce minimum and maximum deposit amounts
  - Track decimal precision per asset
  - Enable/disable assets without contract upgrade

##### 1.1.2 Deposit Function
- **Requirement**: Accept USDC deposits with cross-chain instructions
- **Acceptance Criteria**:
  - Transfer USDC from user to vault securely
  - Generate unique deposit ID from transaction parameters
  - Emit PaymasterDeposit event with all relevant data
  - Support optional message payload for Sapphire execution
  - Validate Sapphire recipient address format

##### 1.1.3 Security Controls
- **Requirement**: Prevent duplicate deposits and ensure fund safety
- **Acceptance Criteria**:
  - Unique deposit ID generation algorithm
  - Re-entrancy protection on all functions
  - Only approved assets can be deposited
  - Proper event emission for off-chain monitoring

#### 1.2 Extensibility Features

##### 1.2.1 Multi-Asset Support
- **Requirement**: Architecture supports future assets without major changes
- **Acceptance Criteria**:
  - Generic deposit function for any ERC-20 token
  - Asset configuration struct with all necessary parameters
  - Standardized event format for all assets
  - Separate approval process for each asset

##### 1.2.2 Admin Functions
- **Requirement**: Controlled management of vault parameters
- **Acceptance Criteria**:
  - Add/remove supported assets
  - Update min/max amounts per asset
  - Pause/unpause deposits in emergency
  - Transfer ownership with two-step process

### 2. Sapphire Chain Components

#### 2.1 Cross-Chain Paymaster Contract

##### 2.1.1 Proof Verification
- **Requirement**: Verify Merkle proofs of Base chain deposits
- **Acceptance Criteria**:
  - Integrate ProvethVerifier for transaction proof validation
  - Verify block hash against oracle attestation
  - Extract and validate deposit parameters from proof
  - Ensure transaction contains expected PaymasterDeposit event

##### 2.1.2 Deposit Processing
- **Requirement**: Process verified deposits and distribute ROSE
- **Acceptance Criteria**:
  - Prevent double-processing with deposit ID tracking
  - Transfer exact ROSE amount to recipient
  - Execute optional message calls after transfer
  - Emit events for successful distributions

##### 2.1.3 Oracle Integration
- **Requirement**: Use blockhash oracle for cross-chain verification
- **Acceptance Criteria**:
  - Query ITrivialBlockHashOracle for Base blockhashes
  - Validate proof blockhash matches oracle data
  - Handle missing blockhash data gracefully
  - Support multiple chain IDs for future expansion

##### 2.1.4 Message Execution
- **Requirement**: Execute arbitrary contract calls with deposits
- **Acceptance Criteria**:
  - Decode target address and calldata from message
  - Execute call after ROSE transfer
  - Emit success/failure events with results
  - Gas limit protection for message execution

#### 2.2 Price Oracle Contract

##### 2.2.1 Price Management
- **Requirement**: Maintain current exchange rates for assets
- **Acceptance Criteria**:
  - Store prices with 8 decimal precision
  - Track last update timestamp
  - Support multiple asset price pairs
  - Implement staleness checks

##### 2.2.2 Access Control
- **Requirement**: Restrict price updates to authorized operators
- **Acceptance Criteria**:
  - Only designated updater can set prices
  - Batch price updates for gas efficiency
  - Event emission for price changes
  - Emergency pause mechanism

### 3. Security Requirements

#### 3.1 Access Control

##### 3.1.1 Role-Based Permissions
- **Requirement**: Implement granular access control
- **Acceptance Criteria**:
  - Owner role for admin functions
  - ROFL operator role for deposit processing
  - Price updater role for oracle updates
  - Role transfer mechanisms

##### 3.1.2 Emergency Controls
- **Requirement**: Ability to pause operations in emergencies
- **Acceptance Criteria**:
  - Pausable deposit acceptance
  - Pausable withdrawal processing
  - Circuit breaker for anomaly detection
  - Time-locked admin actions

#### 3.2 Fund Security

##### 3.2.1 Vault Security
- **Requirement**: Ensure locked funds remain secure
- **Acceptance Criteria**:
  - No unauthorized withdrawal functions
  - Comprehensive event logging
  - Reserve management for future withdrawals
  - Multi-signature considerations

##### 3.2.2 ROSE Management
- **Requirement**: Secure handling of native ROSE tokens
- **Acceptance Criteria**:
  - Receive function for ROSE deposits
  - Protected withdrawal for excess ROSE
  - Balance monitoring capabilities
  - Minimum reserve requirements

## Non-Functional Requirements

### 1. Performance

#### 1.1 Gas Optimization
- Proof verification: <300k gas
- Deposit processing: <400k gas total
- Batch operations where possible
- Efficient storage patterns

#### 1.2 Throughput
- Handle 100+ deposits per hour
- Support future batching mechanisms
- No artificial transaction limits

### 2. Reliability

#### 2.1 Availability
- No single points of failure
- Graceful degradation modes
- Clear error messages
- Comprehensive event logs

#### 2.2 Data Integrity
- Immutable deposit records
- Accurate proof verification
- Consistent state management
- No data corruption risks

### 3. Maintainability

#### 3.1 Code Quality
- Comprehensive documentation
- Modular architecture
- Standard Solidity patterns
- Automated testing

#### 3.2 Upgradeability
- Proxy patterns for critical contracts (optional)
- Migration paths for improvements
- Backward compatibility
- State preservation

## Technical Specifications

### 1. Development Stack

#### Core Technologies
- **Solidity**: 0.8.28
- **Hardhat**: Development framework
- **TypeScript**: Configuration and tests
- **OpenZeppelin**: 5.x contracts

#### Required Dependencies
- **ProvethVerifier**: From liquefaction/contracts/proveth/
- **ITrivialBlockHashOracle**: From contracts/oracle/
- **RLPReader**: Via solidity-rlp npm package
- **OpenZeppelin Contracts**: Standard implementations

### 2. Contract Architecture

#### 2.1 Base Contracts
```solidity
USDCPaymasterVault
├── IERC20 (OpenZeppelin)
├── Ownable (OpenZeppelin)
├── Pausable (OpenZeppelin)
└── ReentrancyGuard (OpenZeppelin)
```

#### 2.2 Sapphire Contracts
```solidity
CrossChainPaymaster
├── ProvethVerifier (Existing)
├── Ownable (OpenZeppelin)
├── EnumerableSet (OpenZeppelin)
└── ITrivialBlockHashOracle (Interface)

SimplePriceOracle
├── Ownable (OpenZeppelin)
└── Pausable (OpenZeppelin)
```

### 3. Data Structures

#### 3.1 Asset Configuration
```solidity
struct AssetConfig {
    bool isActive;
    uint256 minAmount;
    uint256 maxAmount;
    uint8 decimals;
}
```

#### 3.2 Chain Configuration
```solidity
struct ChainConfig {
    address vaultContract;
    uint256 confirmations;
    bool isActive;
}
```

#### 3.3 Deposit Data
```solidity
struct DepositData {
    bytes32 depositId;
    address sender;
    address recipient;
    address asset;
    uint256 chainId;
    uint256 amount;
    uint256 roseAmount;
    bytes message;
    bytes proof;
}
```

## Integration Requirements

### 1. External Contracts

#### 1.1 ProvethVerifier Integration
- Import existing verified contract
- Understand proof format requirements
- Test with various proof types
- Handle verification failures

#### 1.2 Block Hash Oracle
- Interface with existing oracle
- Handle missing block data
- Support multi-chain queries
- Manage gas costs

### 2. Events and Monitoring

#### 2.1 Event Definitions
- PaymasterDeposit (Base)
- RoseDistributed (Sapphire)
- MessageExecution (Sapphire)
- PricesUpdated (Oracle)

#### 2.2 Monitoring Requirements
- Real-time event indexing
- Historical query support
- Cross-chain event correlation
- Performance metrics

## Testing Requirements

### 1. Unit Tests

#### Contract Tests
- Asset configuration management
- Deposit ID generation
- Proof verification logic
- ROSE distribution calculations
- Message execution handling

#### Security Tests
- Reentrancy protection
- Access control enforcement
- Integer overflow/underflow
- Edge case handling

### 2. Integration Tests

#### Cross-Contract Tests
- Vault to paymaster flow
- Oracle integration
- Price calculations
- Multi-asset scenarios

#### End-to-End Tests
- Complete deposit flow
- Proof generation and verification
- Message execution
- Error scenarios

### 3. Gas Optimization Tests
- Measure gas costs per operation
- Identify optimization opportunities
- Batch operation efficiency
- Storage pattern optimization

## Deployment Requirements

### 1. Network Configuration

#### Base Deployment
- Network: Base Mainnet (Chain ID: 8453)
- Required tokens: USDC address
- Gas settings optimization
- Verification on Basescan

#### Sapphire Deployment
- Network: Oasis Sapphire (Chain ID: 23294)
- Confidential state considerations
- Gas pricing differences
- Explorer verification

### 2. Initialization

#### Contract Setup
1. Deploy price oracle first
2. Deploy block hash oracle
3. Deploy paymaster contract
4. Deploy vault contract
5. Configure all contracts
6. Set operator addresses
7. Fund paymaster with ROSE

#### Verification Steps
- Verify all contract code
- Test initial configuration
- Validate access controls
- Confirm oracle connectivity

## Security Audit Requirements

### 1. Audit Scope
- All custom contract code
- Integration points
- Access control logic
- Fund handling mechanisms

### 2. Key Areas
- Proof verification correctness
- Deposit uniqueness guarantees
- ROSE distribution accuracy
- Message execution safety

### 3. Known Considerations
- Integer precision in calculations
- Block timestamp manipulation
- Cross-chain timing attacks
- Oracle reliability

## Success Metrics

### 1. Functional Success
- 100% accurate proof verification
- Zero duplicate deposits processed
- Correct ROSE amounts distributed
- Message execution success rate >95%

### 2. Performance Metrics
- Gas costs within estimates
- Transaction success rate >99%
- Processing time <30 seconds
- Oracle update frequency maintained

### 3. Security Metrics
- Zero security incidents
- No unauthorized access
- All funds accounted for
- Audit findings addressed

## Future Enhancements

### Phase 2 Features
- Batch deposit processing
- Multi-chain support (Ethereum, Arbitrum)
- Additional assets (ETH, USDT)
- Withdrawal mechanism (ROSE → USDC)

### Phase 3 Features
- Decentralized operator set
- Optimistic verification mode
- Dynamic fee adjustments
- Liquidity pool integration

### Architecture Extensions
- Modular chain adapters
- Pluggable verification systems
- Advanced message routing
- Cross-chain liquidity management

## Risk Mitigation

### Technical Risks
- **Proof Complexity**: Extensive testing with various proof types
- **Gas Limitations**: Optimize verification algorithms
- **Oracle Failures**: Implement fallback mechanisms

### Economic Risks
- **Price Volatility**: Frequent oracle updates with bounds
- **Liquidity Shortfalls**: Reserve monitoring and alerts
- **MEV Attacks**: Commit-reveal patterns where applicable

### Operational Risks
- **Operator Compromise**: Multi-signature considerations
- **Contract Bugs**: Comprehensive testing and audits
- **Upgrade Risks**: Careful migration planning

## Acceptance Criteria

The Cross-Chain Paymaster Contracts will be considered complete when:

1. All contracts deploy successfully to testnets
2. End-to-end deposit flow works correctly
3. Gas costs meet specified targets
4. Security audit completed with findings addressed
5. Integration tests pass with >95% coverage
6. Documentation complete and reviewed
7. Mainnet deployment plan approved