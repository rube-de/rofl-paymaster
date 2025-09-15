// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import { ReceiptProof } from "../../hashi/prover/HashiProverStructs.sol";

/**
 * @title ICrossChainPaymaster
 * @notice Interface for the Sapphire CrossChainPaymaster using Hashi receipt proofs
 */
interface ICrossChainPaymaster {
    /**
     * @notice Emitted after a verified payment distributes ROSE on Sapphire
     * @param paymentId Deterministic ID: keccak(chainId, vault, blockNumber, txIndex, logIndex)
     * @param roseAmount Amount of ROSE distributed
     */
    event PaymentProcessed(bytes32 indexed paymentId, uint256 roseAmount);

    /**
     * @notice Emitted when the price oracle address changes
     * @param oldOracle Previous oracle address
     * @param newOracle New oracle address
     */
    event PriceOracleUpdated(address indexed oldOracle, address indexed newOracle);

    /**
     * @notice Process a PaymentInitiated event proof and distribute ROSE (permissionless)
     * @dev Security enforced by Hashi proof verification, chain/vault auth, limits, and replay protection
     * @param proof ReceiptProof consumed by HashiProver
     */
    function processPayment(ReceiptProof calldata proof) external;

    /**
     * @notice Checks if a paymentId has already been processed
     * @param paymentId keccak(chainId, vault, blockNumber, txIndex, logIndex)
     * @return processed True if already processed
     */
    function isPaymentProcessed(bytes32 paymentId) external view returns (bool processed);

    /**
     * @notice Converts a token amount to ROSE via oracle
     * @param token Source chain token address
     * @param tokenAmount Amount of tokens
     * @return roseAmount Equivalent in ROSE
     */
    function calculateRoseAmount(address token, uint256 tokenAmount) external view returns (uint256 roseAmount);

    /**
     * @notice Returns current price oracle address
     */
    function priceOracle() external view returns (address);

    /**
     * @notice Pause/unpause controls
     */
    function pause() external;
    function unpause() external;
    function paused() external view returns (bool);
}
