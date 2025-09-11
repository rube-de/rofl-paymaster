// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/**
 * @title SapphireTypes
 * @notice Data structures and types for Sapphire chain contracts
 * @dev Optimized for Oasis Sapphire privacy features and gas efficiency
 */
library SapphireTypes {
    /**
     * @notice Configuration for supported source chains
     * @dev Packed into single storage slot (256 bits total)
     */
    struct ChainConfig {
        uint32 chainId;         // 32 bits - chain ID (up to 4.2B)
        bool enabled;           // 1 bit - whether chain is enabled
        uint32 confirmations;   // 32 bits - required confirmations
        uint32 blockTime;       // 32 bits - average block time in seconds
        uint128 maxAmount;      // 128 bits - max amount per transaction
        // Total: 32 + 1 + 32 + 32 + 128 = 225 bits (31 bits remaining)
    }

    /**
     * @notice Merkle proof data for cross-chain verification
     * @dev Contains all data needed to verify a deposit proof
     */
    struct ProofData {
        bytes32 blockHash;      // 256 bits - block hash from source chain
        bytes32 receiptRoot;    // 256 bits - receipt root from block header
        bytes32 txHash;         // 256 bits - transaction hash
        bytes rlpEncodedReceipt; // Variable - RLP encoded receipt
        bytes[] merkleProof;    // Variable - merkle proof path
        uint256 logIndex;       // 256 bits - log index in receipt
    }

    /**
     * @notice Processed deposit information
     * @dev Stores verification results and distribution details
     */
    struct ProcessedDeposit {
        uint256 depositId;      // 256 bits - original deposit ID
        uint32 sourceChainId;   // 32 bits - source chain ID for validation
        address sourceToken;    // 160 bits - token address from source chain
        uint256 sourceAmount;   // 256 bits - original deposit amount
        address recipient;      // 160 bits - recipient on Sapphire
        uint256 roseAmount;     // 256 bits - ROSE amount distributed
        uint256 blockNumber;    // 256 bits - block number of processing
        uint256 timestamp;      // 256 bits - timestamp of processing
        bytes32 proofHash;      // 256 bits - hash of the proof used
        bool claimed;           // 1 bit - whether deposit has been claimed (replay protection)
    }

    /**
     * @notice Price feed data from oracle
     * @dev Contains price and metadata for token conversion
     */
    struct PriceData {
        uint256 price;          // 256 bits - price in ROSE (scaled by 10^18)
        uint256 timestamp;      // 256 bits - when price was last updated
        uint256 confidence;     // 256 bits - confidence score (0-100)
        bool isActive;          // 1 bit - whether price feed is active
    }

    /**
     * @notice ROSE distribution limits and circuit breaker
     * @dev Gas-optimized packing for distribution controls
     */
    struct DistributionLimits {
        uint128 dailyLimit;     // 128 bits - daily ROSE distribution limit
        uint128 currentDaily;   // 128 bits - current daily distribution
        uint128 perTxLimit;      // 128 bits - per-transaction limit
        uint32 lastResetDay;    // 32 bits - last reset day
        bool enabled;           // 1 bit - whether limits are enforced
        // Total: 128 + 128 + 128 + 32 + 1 = 417 bits (requires 3 slots)
    }

    /**
     * @notice Cross-chain message execution data
     * @dev For executing messages on Sapphire after deposit verification
     */
    struct MessageData {
        address target;         // 160 bits - contract to call
        uint256 value;          // 256 bits - ETH/ROSE value to send
        bytes data;             // Variable - call data
        uint256 gasLimit;       // 256 bits - gas limit for execution
        bool executed;          // 1 bit - whether message was executed
    }

    /**
     * @notice Price configuration with configurable thresholds
     * @dev Replaces hardcoded values for better governance
     */
    struct PriceConfig {
        uint256 stalenessThreshold;    // Maximum age in seconds
        uint256 minConfidence;         // Minimum confidence percentage (0-100)
        uint256 maxDeviation;          // Maximum price deviation percentage
    }

    /**
     * @notice Rounding options for token conversions
     * @dev Prevents precision loss in calculations
     */
    enum Rounding {
        Down,    // Round down (floor)
        Up,      // Round up (ceiling)
        Nearest  // Round to nearest
    }

    /**
     * @notice Custom errors for validation
     */
    error InvalidChainId();
    error InvalidTokenDecimals();
    error InvalidPriceData();
    error TokenAmountOverflow();
    error PriceDataOverflow();
    error DepositAlreadyClaimed();
    error UnauthorizedChain();

    /**
     * @notice Validates chain configuration with comprehensive checks
     * @param config Chain configuration to validate
     * @return valid True if configuration is valid
     */
    function validateChainConfig(ChainConfig memory config) internal pure returns (bool valid) {
        if (config.chainId == 0) revert InvalidChainId();
        if (config.confirmations == 0) return false;
        if (config.blockTime == 0) return false;
        if (config.maxAmount == 0) return false;
        return true;
    }

    /**
     * @notice Validates that a deposit is from an authorized chain
     * @param sourceChainId Chain ID from the deposit
     * @param authorizedChains Array of authorized chain configurations
     * @return valid True if chain is authorized
     */
    function validateSourceChain(
        uint32 sourceChainId,
        ChainConfig[] memory authorizedChains
    ) internal pure returns (bool valid) {
        if (sourceChainId == 0) revert InvalidChainId();
        
        for (uint256 i = 0; i < authorizedChains.length; i++) {
            if (authorizedChains[i].chainId == sourceChainId && authorizedChains[i].enabled) {
                return true;
            }
        }
        revert UnauthorizedChain();
    }

    /**
     * @notice Validates proof data structure
     * @param proof Proof data to validate
     * @return valid True if proof structure is valid
     */
    function validateProofData(ProofData memory proof) internal pure returns (bool valid) {
        return proof.blockHash != bytes32(0) &&
               proof.receiptRoot != bytes32(0) &&
               proof.txHash != bytes32(0) &&
               proof.rlpEncodedReceipt.length > 0 &&
               proof.merkleProof.length > 0;
    }

    /**
     * @notice Checks if price data is stale using configurable thresholds
     * @param priceData Price data to check
     * @param config Price configuration with thresholds
     * @return stale True if price is too old or unreliable
     */
    function isPriceStale(
        PriceData memory priceData,
        PriceConfig memory config
    ) internal view returns (bool stale) {
        return !priceData.isActive || 
               (block.timestamp - priceData.timestamp) > config.stalenessThreshold ||
               priceData.confidence < config.minConfidence;
    }

    /**
     * @notice Legacy function for backward compatibility
     * @param priceData Price data to check
     * @param stalenessThreshold Maximum age in seconds
     * @return stale True if price is too old
     */
    function isPriceStale(
        PriceData memory priceData,
        uint256 stalenessThreshold
    ) internal view returns (bool stale) {
        return !priceData.isActive || 
               (block.timestamp - priceData.timestamp) > stalenessThreshold ||
               priceData.confidence < 80; // Legacy 80% minimum confidence
    }

    /**
     * @notice Updates distribution limits after ROSE distribution
     * @param limits Current limits
     * @param amount Amount being distributed
     * @return updated Updated limits
     */
    function updateDistributionLimits(
        DistributionLimits memory limits,
        uint128 amount
    ) internal view returns (DistributionLimits memory updated) {
        uint32 currentDay = uint32(block.timestamp / 86400);
        
        if (currentDay > limits.lastResetDay) {
            // New day - reset daily counter
            updated = DistributionLimits({
                dailyLimit: limits.dailyLimit,
                currentDaily: amount,
                perTxLimit: limits.perTxLimit,
                lastResetDay: currentDay,
                enabled: limits.enabled
            });
        } else {
            // Same day - add to current daily amount
            updated = limits;
            updated.currentDaily += amount;
        }
    }

    /**
     * @notice Checks if distribution would exceed limits
     * @param limits Current distribution limits
     * @param amount Amount to be distributed
     * @return wouldExceed True if limits would be exceeded
     */
    function wouldExceedLimits(
        DistributionLimits memory limits,
        uint128 amount
    ) internal view returns (bool wouldExceed) {
        if (!limits.enabled) return false;
        
        // Check per-transaction limit
        if (amount > limits.perTxLimit) return true;
        
        uint32 currentDay = uint32(block.timestamp / 86400);
        
        // Check daily limit
        if (currentDay > limits.lastResetDay) {
            // New day - only check against daily limit
            return amount > limits.dailyLimit;
        } else {
            // Same day - check against remaining daily limit
            return (limits.currentDaily + amount) > limits.dailyLimit;
        }
    }

    /**
     * @notice Calculates ROSE amount from token amount with precision options
     * @dev Uses Solidity 0.8+ built-in overflow protection
     * @param tokenAmount Amount of source tokens
     * @param tokenDecimals Decimals of source token
     * @param priceData Price data for conversion
     * @param rounding Rounding option for precision
     * @return roseAmount Equivalent amount in ROSE
     */
    function calculateRoseAmount(
        uint256 tokenAmount,
        uint8 tokenDecimals,
        PriceData memory priceData,
        Rounding rounding
    ) internal pure returns (uint256 roseAmount) {
        if (!priceData.isActive || priceData.price == 0) revert InvalidPriceData();
        if (tokenDecimals > 18) revert InvalidTokenDecimals();
        
        // Convert token amount to 18 decimal standard, then apply price
        // Solidity 0.8+ will automatically revert on overflow
        uint256 normalizedAmount;
        if (tokenDecimals < 18) {
            normalizedAmount = tokenAmount * (10 ** (18 - tokenDecimals));
        } else {
            normalizedAmount = tokenAmount;
        }
        
        return _applyRounding((normalizedAmount * priceData.price) / 1e18, 
                            (normalizedAmount * priceData.price) % 1e18, 
                            1e18, 
                            rounding);
    }

    /**
     * @notice Legacy function for backward compatibility
     * @param tokenAmount Amount of source tokens
     * @param tokenDecimals Decimals of source token
     * @param priceData Price data for conversion
     * @return roseAmount Equivalent amount in ROSE
     */
    function calculateRoseAmount(
        uint256 tokenAmount,
        uint8 tokenDecimals,
        PriceData memory priceData
    ) internal pure returns (uint256 roseAmount) {
        return calculateRoseAmount(tokenAmount, tokenDecimals, priceData, Rounding.Down);
    }

    /**
     * @notice Applies rounding to a division result
     * @param quotient Base quotient from division
     * @param remainder Remainder from division
     * @param divisor Original divisor
     * @param rounding Rounding option
     * @return result Final result with rounding applied
     */
    function _applyRounding(
        uint256 quotient,
        uint256 remainder,
        uint256 divisor,
        Rounding rounding
    ) private pure returns (uint256 result) {
        if (rounding == Rounding.Down || remainder == 0) {
            return quotient;
        } else if (rounding == Rounding.Up) {
            return quotient + 1;
        } else { // Rounding.Nearest
            return remainder >= divisor / 2 ? quotient + 1 : quotient;
        }
    }

    /**
     * @notice Generates hash of proof data for uniqueness checking
     * @param proof Proof data to hash
     * @return proofHash Unique hash of the proof
     */
    function hashProofData(ProofData memory proof) internal pure returns (bytes32 proofHash) {
        return keccak256(abi.encodePacked(
            proof.blockHash,
            proof.receiptRoot,
            proof.txHash,
            keccak256(proof.rlpEncodedReceipt),
            proof.logIndex
        ));
    }
}