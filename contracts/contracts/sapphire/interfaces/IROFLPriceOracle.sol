// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/**
 * @title IROFLPriceOracle
 * @notice Interface for the ROFL-based price oracle providing token/ROSE exchange rates
 * @dev Supports multiple ERC20 tokens with configurable price feeds and role-based access control
 * 
 * Access Control Requirements:
 * - ORACLE_UPDATER_ROLE: Can update token prices
 * - ORACLE_ADMIN_ROLE: Can add/remove token feeds and configure thresholds
 * - EMERGENCY_STOP_ROLE: Can pause/unpause oracle operations
 * - Multi-sig required for admin operations
 */
interface IROFLPriceOracle {
    /**
     * @notice Emitted when a token price is updated
     * @param token The token address
     * @param price The new price in ROSE (scaled by 10^18)
     * @param timestamp The timestamp of the price update
     * @param blockNumber Block number of update (indexed for range queries)
     * @param confidence Confidence score of the price update
     */
    event PriceUpdated(
        address indexed token,
        uint256 price,
        uint256 timestamp,
        uint256 indexed blockNumber,
        uint256 confidence
    );

    /**
     * @notice Emitted when a new token price feed is added
     * @param token The token address
     * @param initialPrice The initial price in ROSE
     * @param decimals The token's decimals
     */
    event TokenFeedAdded(
        address indexed token,
        uint256 initialPrice,
        uint8 decimals
    );

    /**
     * @notice Emitted when a token price feed is removed
     * @param token The token address
     */
    event TokenFeedRemoved(address indexed token);

    /**
     * @notice Emitted when oracle configuration is updated
     * @param stalenessThreshold New staleness threshold
     * @param minConfidence New minimum confidence threshold
     */
    event OracleConfigUpdated(
        uint256 stalenessThreshold,
        uint256 minConfidence
    );

    /**
     * @notice Emitted when oracle is paused/unpaused
     * @param paused Whether oracle is paused
     * @param timestamp When the change occurred
     */
    event OraclePauseStatusChanged(
        bool paused,
        uint256 timestamp
    );

    /**
     * @notice Gets the current price of a token in ROSE
     * @param token The token address to query
     * @return price The price in ROSE (scaled by 10^18)
     * @return timestamp The timestamp of the last price update
     */
    function getPrice(address token) external view returns (
        uint256 price,
        uint256 timestamp
    );

    /**
     * @notice Converts a token amount to ROSE amount
     * @param token The token address
     * @param tokenAmount The amount of tokens
     * @return roseAmount The equivalent amount in ROSE
     */
    function convertToRose(
        address token,
        uint256 tokenAmount
    ) external view returns (uint256 roseAmount);

    /**
     * @notice Converts a ROSE amount to token amount
     * @param token The token address
     * @param roseAmount The amount of ROSE
     * @return tokenAmount The equivalent amount in tokens
     */
    function convertFromRose(
        address token,
        uint256 roseAmount
    ) external view returns (uint256 tokenAmount);

    /**
     * @notice Checks if a token has an active price feed
     * @param token The token address to check
     * @return supported True if the token has a price feed
     */
    function isTokenSupported(address token) external view returns (bool supported);

    /**
     * @notice Checks if a price is stale (too old)
     * @param token The token address to check
     * @return stale True if the price is older than the staleness threshold
     */
    function isPriceStale(address token) external view returns (bool stale);

    /**
     * @notice Gets the staleness threshold in seconds
     * @return threshold Maximum age for a price before it's considered stale
     */
    function stalenessThreshold() external view returns (uint256 threshold);

    /**
     * @notice Gets the decimals for a token
     * @param token The token address
     * @return decimals The number of decimals
     */
    function getTokenDecimals(address token) external view returns (uint8 decimals);

    /**
     * @notice Updates the price for a token
     * @dev MUST be restricted to ORACLE_UPDATER_ROLE
     * @dev MUST implement nonReentrant modifier
     * @dev MUST validate price data before update
     * @param token The token address
     * @param price The new price in ROSE (scaled by 10^18)
     * @param confidence Confidence score (0-100)
     */
    function updatePrice(
        address token, 
        uint256 price,
        uint256 confidence
    ) external;

    /**
     * @notice Updates multiple token prices in one transaction
     * @dev MUST be restricted to ORACLE_UPDATER_ROLE
     * @dev MUST implement nonReentrant modifier
     * @param tokens Array of token addresses
     * @param prices Array of prices in ROSE (scaled by 10^18)
     * @param confidences Array of confidence scores (0-100)
     */
    function updatePrices(
        address[] calldata tokens,
        uint256[] calldata prices,
        uint256[] calldata confidences
    ) external;

    /**
     * @notice Pauses all oracle operations
     * @dev MUST be restricted to EMERGENCY_STOP_ROLE
     */
    function pauseOracle() external;

    /**
     * @notice Unpauses oracle operations
     * @dev MUST be restricted to EMERGENCY_STOP_ROLE
     */
    function unpauseOracle() external;

    /**
     * @notice Adds a new token price feed
     * @dev MUST be restricted to ORACLE_ADMIN_ROLE
     * @dev MUST require multi-sig approval
     * @param token Token address
     * @param initialPrice Initial price in ROSE
     * @param decimals Token decimals
     */
    function addTokenFeed(
        address token,
        uint256 initialPrice,
        uint8 decimals
    ) external;

    /**
     * @notice Removes a token price feed
     * @dev MUST be restricted to ORACLE_ADMIN_ROLE
     * @dev MUST require multi-sig approval
     * @param token Token address to remove
     */
    function removeTokenFeed(address token) external;

    /**
     * @notice Updates oracle configuration
     * @dev MUST be restricted to ORACLE_ADMIN_ROLE
     * @dev MUST require multi-sig approval
     * @param stalenessThreshold New staleness threshold
     * @param minConfidence Minimum confidence threshold
     */
    function updateOracleConfig(
        uint256 stalenessThreshold,
        uint256 minConfidence
    ) external;

    /**
     * @notice Checks if oracle is currently paused
     * @return paused True if oracle is paused
     */
    function isPaused() external view returns (bool paused);
}