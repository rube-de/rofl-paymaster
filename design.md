# Design: Cross-Chain Paymaster (Hashi)

## Overview

This system lets users deposit an ERC20 (e.g., USDC) on a remote EVM chain (e.g., Base) and receive ROSE on Oasis Sapphire. It relies on Hashi receipt proofs verified against ShoyuBashi, so anyone can relay a valid proof permissionlessly on Sapphire.

Core idea:
- On the remote chain, `PaymasterVault` records deposits and emits a minimal `PaymentInitiated` event plus a richer `TokenDeposited` event. It also requests the block header via `BlockHeaderRequester` so Hashi oracles publish it to ShoyuBashi.
- Off-chain, a relayer (or any user) builds a receipts-trie proof (`ReceiptProof`) for the `PaymentInitiated` log.
- On Sapphire, anyone calls `CrossChainPaymaster.processPayment(ReceiptProof)` to verify the event, convert the token amount to ROSE via a price oracle, and transfer ROSE to the intended recipient.

## Contracts

- Remote chain (e.g., Base)
  - `contracts/contracts/remote/PaymasterVault.sol`: upgradeable vault that accepts ERC20 deposits, enforces token bounds and per-token circuit breakers, emits `PaymentInitiated`, and requests block headers.
  - `contracts/contracts/remote/BlockHeaderRequester.sol`: helper that emits header requests consumed by Hashi adapters.

- Hashi (oracle aggregation)
  - `contracts/contracts/hashi/*`: ShoyuBashi + adapters + prover libraries used to verify foreign logs via receipt proofs.

- Sapphire (Oasis)
  - `contracts/contracts/sapphire/CrossChainPaymaster.sol`: upgradeable paymaster that verifies `PaymentInitiated` events and distributes ROSE based on a price oracle, with per-tx and daily limits, chain config, and vault authorization.
  - `contracts/contracts/sapphire/interfaces/IROFLPriceOracle.sol`: conversion interface used by the paymaster.

## Data Flow

1) Deposit on remote chain
- User calls `PaymasterVault.deposit(IERC20 token, uint256 amount, address recipient)`.
- Validates token config and circuit breaker. Pulls tokens. Emits:
  - `TokenDeposited(uint256 depositId, address depositor, address token, uint256 amount, address recipient, uint256 blockNumber)`
  - `PaymentInitiated(address payer, address recipient, address token, uint256 amount, bytes32 paymentId)`
- Calls `BlockHeaderRequester.requestBlockHeader(chainId, blockNumber, paymentId)` to prompt oracles to publish the header to ShoyuBashi.

2) Build proof off-chain
- After confirmations, generate a Hashi `ReceiptProof` for the tx that emitted `PaymentInitiated` using the provided Hardhat task.
- The proof binds the exact block header, receipts trie, transaction index, and the log index of `PaymentInitiated`.

3) Relay on Sapphire
- Anyone submits `CrossChainPaymaster.processPayment(ReceiptProof)`.
- The paymaster verifies the log against ShoyuBashi (multi-oracle consensus), ensures the source chain is enabled and the source vault is authorized, derives a canonical `paymentId`, checks replay and limits, converts to ROSE via the oracle, and transfers ROSE to the recipient.

## Proof Type (ReceiptProof)

ReceiptProof is defined in `contracts/contracts/hashi/prover/HashiProverStructs.sol` and encoded by the tooling as an array when written to JSON:

[chainId, blockNumber, blockHeader, ancestralBlockNumber, ancestralBlockHeaders[], receiptProof[], transactionIndex, logIndex]

- `chainId`: number
- `blockNumber`: number
- `blockHeader`: RLP-serialized block header (hex string)
- `ancestralBlockNumber`: number (unused in this flow; 0)
- `ancestralBlockHeaders`: string[] (unused; empty array)
- `receiptProof`: string[] (Merkle proof nodes for the receipts trie)
- `transactionIndex`: string (RLP-encoded index as hex, per Ethereum receipt trie spec)
- `logIndex`: number (index of the PaymentInitiated log in the receipt)

## Canonical Payment ID

The paymaster derives a deterministic identifier used for replay protection and auditability:

paymentId = keccak(chainId, vault, blockNumber, txIndex, logIndex)

Where `txIndex` is decoded from the RLP-encoded `transactionIndex` provided in the proof. This ID is independent of any contextual IDs emitted on the source chain.

## Security Model

- Cryptographic verification: Hashi verifies the exact `PaymentInitiated` log against ShoyuBashi-published block headers and receipts roots.
- Authorized chains and vaults: Only events from enabled chains and authorized source vaults are honored.
- Replay protection: `processedPayments[paymentId]` prevents double distribution.
- Distribution limits: Per-tx and daily limits enforced with automatic daily reset.
- Pausable and upgradeable: Owner (and operator for some ops) can pause/unpause and upgrade via UUPS.

## Configuration and Operations

Deployment tasks (Sapphire)
- `deploy:cross-chain-paymaster` – deploy UUPS proxy with owner, operator, price oracle, ShoyuBashi address, and initial limits.
- `configure:cross-chain-paymaster` – enable chain, set confirmations/block time/max amount, authorize source vault(s), adjust distribution limits.

Deployment tasks (Remote)
- `deploy:paymaster-vault` – deploy UUPS proxy with owner and `BlockHeaderRequester`.
- `configure:paymaster-vault` – configure token min/max, enable, decimals, and per-token circuit breaker daily limits.

End-to-end operations
- Deposit on remote:
  - `bunx hardhat pay:deposit --network <remote> --vault <vault> --token <erc20> --amount <whole> --recipient <sapphireAddress> --approve`
- Generate proof on remote:
  - `bunx hardhat pay:generate-proof --network <remote> --tx-hash <depositTxHash>`
- Relay on Sapphire:
  - `bunx hardhat pay:relay --network <sapphire> --paymaster <paymasterProxy> --proof proof.json`

Mock vs Production ShoyuBashi
- Production: wait several minutes for multi-oracle consensus after deposit before relaying.
- Mock: post blockhash manually using `contracts/tasks/post-blockhash.ts` before relaying.

## Price Conversion

`CrossChainPaymaster` queries `IROFLPriceOracle` to convert source token amounts into ROSE. The oracle encapsulates token decimals, price staleness checks, and governance of feeds. The paymaster exposes `calculateRoseAmount(token, amount)` as a convenience view.

## Files of Interest

- Remote chain
  - `contracts/contracts/remote/PaymasterVault.sol`
  - `contracts/contracts/remote/BlockHeaderRequester.sol`

- Sapphire
  - `contracts/contracts/sapphire/CrossChainPaymaster.sol`
  - `contracts/contracts/sapphire/interfaces/IROFLPriceOracle.sol`

- Hashi core
  - `contracts/contracts/hashi/prover/HashiProverUpgradeable.sol`
  - `contracts/contracts/hashi/prover/HashiProverStructs.sol`
  - `contracts/contracts/hashi/Yaru.sol`

- Tasks
  - `contracts/tasks/paymaster/pay/deposit-token.ts`
  - `contracts/tasks/paymaster/pay/generate-proof.ts`
  - `contracts/tasks/paymaster/pay/relay-payment.ts`
  - `contracts/tasks/post-blockhash.ts` (mock-only)

## Future Extensions

- Additional source chains and tokens
- Proof batching for gas optimization
- Message execution payloads on Sapphire (post-distribution hooks)
- Automatic relayer service with monitoring and retries

