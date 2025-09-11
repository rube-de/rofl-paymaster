// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/**
 * @title ICrossChainPaymaster
 * @notice Interface for the CrossChainPaymaster contract on Oasis Sapphire chain
 * @dev Handles cross-chain proof verification and ROSE distribution
 */
interface ICrossChainPaymaster {
    /**
     * @notice Emitted when a cross-chain deposit is successfully verified and ROSE is distributed
     * @param depositId Original deposit ID from Base chain
     * @param depositor Original depositor address on Base chain
     * @param token Original token address deposited on Base chain
     * @param amount Amount of original tokens deposited
     * @param recipient Recipient address on Sapphire chain
     * @param roseAmount Amount of ROSE distributed
     * @param blockNumber Block number of verification (indexed for range queries)
     */
    event DepositVerified(
        uint256 depositId,
        address indexed depositor,
        address indexed token,
        uint256 amount,
        address indexed recipient,
        uint256 roseAmount,
        uint256 blockNumber
    );

    /**
     * @notice Emitted when a deposit claim fails verification
     * @param depositId Attempted deposit ID
     * @param claimer Address attempting the claim
     * @param reason Failure reason
     */
    event VerificationFailed(
        uint256 depositId,
        address indexed claimer,
        string reason
    );

    /**
     * @notice Emitted when the price oracle is updated
     * @param oldOracle Previous oracle address
     * @param newOracle New oracle address
     */
    event PriceOracleUpdated(
        address indexed oldOracle,
        address indexed newOracle
    );

    /**
     * @notice Emitted when the block hash oracle is updated
     * @param oldOracle Previous oracle address
     * @param newOracle New oracle address
     */
    event BlockHashOracleUpdated(
        address indexed oldOracle,
        address indexed newOracle
    );

    /**
     * @notice Verifies a cross-chain deposit and distributes ROSE tokens
     * @dev MUST use nonReentrant modifier to prevent reentrancy attacks
     * @dev MUST use whenNotPaused modifier to respect pause state
     * @dev MUST atomically: verify proof, check unclaimed, mark claimed, distribute ROSE
     * @dev MUST revert if deposit is already claimed (replay protection)
     * @dev MUST follow Checks-Effects-Interactions pattern
     * @param depositId The deposit ID from Base chain
     * @param depositor Original depositor address
     * @param token Original token address
     * @param amount Original deposit amount
     * @param recipient Recipient address on Sapphire
     * @param blockNumber Block number of the deposit on Base
     * @param proof Merkle proof for verification
     */
    function verifyAndDistribute(
        uint256 depositId,
        address depositor,
        address token,
        uint256 amount,
        address recipient,
        uint256 blockNumber,
        bytes calldata proof
    ) external;

    /**
     * @notice Checks if a deposit has already been claimed
     * @param depositId The deposit ID to check
     * @return claimed True if the deposit has been claimed
     */
    function isDepositClaimed(uint256 depositId) external view returns (bool claimed);

    /**
     * @notice Gets the amount of ROSE that would be distributed for a token amount
     * @param token The token address from Base chain
     * @param tokenAmount The amount of tokens
     * @return roseAmount The equivalent amount of ROSE
     */
    function calculateRoseAmount(
        address token,
        uint256 tokenAmount
    ) external view returns (uint256 roseAmount);

    /**
     * @notice Gets the current price oracle address
     * @return oracle The price oracle contract address
     */
    function priceOracle() external view returns (address oracle);

    /**
     * @notice Gets the current block hash oracle address
     * @return oracle The block hash oracle contract address
     */
    function blockHashOracle() external view returns (address oracle);

    /**
     * @notice Gets the Merkle proof verifier address
     * @return verifier The proof verifier contract address
     */
    function proofVerifier() external view returns (address verifier);

    /**
     * @notice Pauses the contract (emergency use only)
     */
    function pause() external;

    /**
     * @notice Unpauses the contract
     */
    function unpause() external;

    /**
     * @notice Checks if the contract is paused
     * @return paused True if paused
     */
    function paused() external view returns (bool paused);
}
