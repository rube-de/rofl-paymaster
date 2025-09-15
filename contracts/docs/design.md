# Design Document: Cross-Chain Paymaster (Hashi)

## 1. System Overview

The system lets users deposit an ERC20 (e.g., USDC) on a remote EVM chain (e.g., Base) and receive ROSE on Oasis Sapphire. It uses Hashi receipt proofs verified against ShoyuBashi, enabling permissionless relaying of valid events to Sapphire.

- Remote chain vault accepts deposits and emits a minimal `PaymentInitiated` event plus a richer `TokenDeposited` event.
- Hashi oracles publish the relevant block headers to ShoyuBashi.
- A relayer (or any user) builds a `ReceiptProof` over the receipts trie for the `PaymentInitiated` log.
- On Sapphire, `CrossChainPaymaster.processPayment` verifies the proof, checks policy, converts to ROSE via a price oracle, and transfers ROSE to the recipient.

## 2. Components

- Remote chain (e.g., Base)
  - `PaymasterVault` (UUPS): accepts ERC20, enforces token bounds and per-token circuit breaker, emits events, requests block headers.
  - `BlockHeaderRequester`: helper that emits header requests for Hashi adapters.

- Hashi (oracle aggregation)
  - ShoyuBashi + adapters + prover libs (this repo under `contracts/contracts/hashi/*`).

- Sapphire (Oasis)
  - `CrossChainPaymaster` (UUPS): verifies `PaymentInitiated` events via Hashi, converts to ROSE using `IROFLPriceOracle`, enforces distribution limits, policy, and replay protection.
  - `IROFLPriceOracle`: price conversion interface used by the paymaster.

## 3. Data Flow

1) Deposit on remote chain
- Call `PaymasterVault.deposit(IERC20 token, uint256 amount, address recipient)`
- Validates asset config and per-token circuit breaker; pulls tokens via `safeTransferFrom`.
- Emits:
  - `TokenDeposited(uint256 depositId, address depositor, address token, uint256 amount, address recipient, uint256 blockNumber)`
  - `PaymentInitiated(address payer, address recipient, address token, uint256 amount, bytes32 paymentId)`
- Triggers `BlockHeaderRequester.requestBlockHeader(chainId, blockNumber, paymentId)`

2) Build proof off-chain
- After sufficient confirmations, build a Hashi `ReceiptProof` for the transaction and specific `PaymentInitiated` log index.
- The proof commits to: block header, receipts root, tx index (RLP-encoded), and log index.

3) Relay on Sapphire
- Anyone calls `CrossChainPaymaster.processPayment(ReceiptProof proof)`.
- The paymaster verifies via HashiProver/ShoyuBashi, checks chain enabled and vault authorized, derives a canonical `paymentId`, checks replay and limits, converts to ROSE, and transfers to the recipient.

## 4. Proof Type (ReceiptProof)

`ReceiptProof` is defined in `contracts/contracts/hashi/prover/HashiProverStructs.sol`. When serialized to JSON by the tasks, it appears as:

[`chainId`, `blockNumber`, `blockHeader`, `ancestralBlockNumber`, `ancestralBlockHeaders[]`, `receiptProof[]`, `transactionIndex`, `logIndex`]

- `chainId`: number
- `blockNumber`: number
- `blockHeader`: hex string, RLP-encoded block header
- `ancestralBlockNumber`: number (unused in this flow)
- `ancestralBlockHeaders`: string[] (unused)
- `receiptProof`: string[] (Merkle proof nodes for the receipts trie)
- `transactionIndex`: string (RLP-encoded index as hex)
- `logIndex`: number (index of `PaymentInitiated` log inside the receipt)

## 5. Canonical Payment ID

Deterministic `paymentId` used for replay protection and auditability:

`paymentId = keccak(chainId, vault, blockNumber, txIndex, logIndex)`

- `txIndex` is decoded from the RLP-encoded `transactionIndex` in the proof.

## 6. Security Model

- Cryptographic verification: verifies the exact `PaymentInitiated` log against ShoyuBashi-published headers and receipts roots.
- Authorized chains and vaults: only allowed if chain is enabled and source vault is authorized.
- Replay protection: `processedPayments[paymentId]` prevents double distribution.
- Distribution limits: per-tx and daily caps with daily reset.
- Pausable and upgradeable (UUPS): owner-controlled admin and safe upgrades.

## 7. Contract APIs

Remote chain: `PaymasterVault`
- `deposit(IERC20 token, uint256 amount, address recipient)` → `uint256 depositId`
- `setTokenConfig(token, cfg)`
- `setTokenEnabled(token, enabled)`
- `setTokenDailyLimit(token, daily)`
- `setTokenCircuitBreakerEnabled(token, enabled)`
- `withdrawToken(token, to, amount)`
- Events: `TokenDeposited`, `PaymentInitiated`

Sapphire: `CrossChainPaymaster`
- `processPayment(ReceiptProof proof)` permissionless (`nonReentrant`, `whenNotPaused`)
- `calculateRoseAmount(token, tokenAmount)` view
- `setPriceOracle(address)`
- `setChainConfig(chainId, ChainConfig)`
- `setVaultAuthorization(chainId, vault, authorized)`
- `setDistributionLimits(dailyLimit, perTxLimit, enabled)`
- `pause()`/`unpause()`
- Events: `PaymentProcessed`, `PriceOracleUpdated`, `ChainConfigUpdated`, `VaultAuthorizationUpdated`, `DistributionLimitsUpdated`

## 8. Configuration & Tasks

Sapphire deployment
- `bunx hardhat deploy:cross-chain-paymaster --network <sapphire> --owner <addr> --oracle <addr> --shoyubashi <addr> --daily <rose> --pertx <rose> --enabled true`

Sapphire post-deploy
- `bunx hardhat configure:cross-chain-paymaster --network <sapphire> --proxy <paymaster> --chainid <id> --enabled true --confirmations <n> --blocktime <sec> --maxrose <rose>`
- `bunx hardhat configure:cross-chain-paymaster --network <sapphire> --proxy <paymaster> --chainid <id> --vault <vault> --authorize true`
- `bunx hardhat configure:cross-chain-paymaster --network <sapphire> --proxy <paymaster> --daily <rose> --pertx <rose> --limitsenabled true`

Remote deployment
- `bunx hardhat deploy:paymaster-vault --network <remote> --owner <addr> --bhr <BlockHeaderRequester>`
- `bunx hardhat configure:paymaster-vault --network <remote> --proxy <vault> --token <erc20> --enabled true --decimals <n> --min <whole> --max <whole> --dailylimit <whole> --breakerenabled true`

Operational flow
- Deposit: `bunx hardhat pay:deposit --network <remote> --vault <vault> --token <erc20> --amount <whole> --recipient <sapphireAddr> --approve`
- Generate proof: `bunx hardhat pay:generate-proof --network <remote> --tx-hash <depositTxHash>`
- Relay: `bunx hardhat pay:relay --network <sapphire> --paymaster <paymaster> --proof proof.json`

Mock vs Production ShoyuBashi
- Production: wait for oracle consensus (several minutes) after deposit before relaying.
- Mock: post block hash manually on Sapphire using `contracts/tasks/post-blockhash.ts`.

## 9. Errors & Failure Modes (Sapphire)

- `ChainDisabled(chainId)`: source chain not enabled
- `VaultNotAuthorized(chainId, vault)`: vault not authorized for chain
- `InvalidEvent`: RLP log data did not match `PaymentInitiated` signature/shape
- `DuplicatePayment(paymentId)`: payment already processed
- `DistributionLimitExceeded`: per-tx or daily limit would be exceeded
- `TransferFailed`: ROSE transfer failed

## 10. Files of Interest

- Remote chain
  - `contracts/contracts/remote/PaymasterVault.sol`
  - `contracts/contracts/remote/BlockHeaderRequester.sol`

- Sapphire
  - `contracts/contracts/sapphire/CrossChainPaymaster.sol`
  - `contracts/contracts/sapphire/interfaces/IROFLPriceOracle.sol`

- Hashi
  - `contracts/contracts/hashi/prover/HashiProverUpgradeable.sol`
  - `contracts/contracts/hashi/prover/HashiProverStructs.sol`
  - `contracts/contracts/hashi/Yaru.sol` (and adapters)

- Tasks
  - `contracts/tasks/paymaster/pay/deposit-token.ts`
  - `contracts/tasks/paymaster/pay/generate-proof.ts`
  - `contracts/tasks/paymaster/pay/relay-payment.ts`
  - `contracts/tasks/post-blockhash.ts` (mock-only)

## 11. Future Extensions

- Additional source chains and tokens
- Proof batching for gas optimization
- Message execution payloads post-distribution
- Automated relayer service with monitoring and retries
