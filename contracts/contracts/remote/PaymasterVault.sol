// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {OwnableUpgradeable} from "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {ReentrancyGuardUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";

import {IPaymasterVault} from "./interfaces/IPaymasterVault.sol";
import {BlockHeaderRequester} from "./BlockHeaderRequester.sol";
import {RemoteTypes} from "./libraries/RemoteTypes.sol";

/**
 * @title PaymasterVault
 * @notice Remote-chain (Base) vault that accepts ERC20 deposits for cross-chain ROSE distribution on Sapphire.
 *         Emits Hashi-verifiable event and requests block header publication via BlockHeaderRequester.
 */
contract PaymasterVault is
    Initializable,
    UUPSUpgradeable,
    OwnableUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    IPaymasterVault
{
    using SafeERC20 for IERC20;

    // ---------------------------------------------------------------------
    // Events (Hashi-friendly minimal event for proof on Sapphire)
    // ---------------------------------------------------------------------
    /**
     * @notice Emitted for Hashi proofing of a payment initiation.
     * @dev Three indexed topics for efficient filtering; unindexed data carries amount and context.
     * @param payer Address depositing on the remote chain
     * @param recipient Recipient address on Sapphire
     * @param token ERC20 token deposited
     * @param amount Amount of tokens deposited (unindexed, in token decimals)
     * @param paymentId Correlation identifier used as header request context
     */
    event PaymentInitiated(
        address indexed payer,
        address indexed recipient,
        address indexed token,
        uint256 amount,
        bytes32 paymentId
    );

    // ---------------------------------------------------------------------
    // Storage
    // ---------------------------------------------------------------------

    // Supported asset configuration
    mapping(IERC20 => RemoteTypes.AssetConfig) private _assetConfigs;

    // Aggregate volume per token
    mapping(IERC20 => uint256) private _totalDeposited;

    // Deposits by generated ID
    mapping(uint256 => RemoteTypes.DepositData) private _deposits;

    // Per-user nonce used in depositId entropy
    mapping(address => uint256) private _nonces;

    // Circuit breaker state per token (daily limit per asset)
    mapping(IERC20 => RemoteTypes.CircuitBreaker) private _tokenCircuitBreaker;

    // Address of the helper that emits header requests for Hashi oracles
    BlockHeaderRequester public blockHeaderRequester;

    // ---------------------------------------------------------------------
    // Errors
    // ---------------------------------------------------------------------
    error UnsupportedToken();
    error AmountBelowMinimum();
    error AmountAboveMaximum();
    error InvalidRecipient();
    error CircuitBreakerTriggered();
    error ZeroAddress();
    error InvalidAmount();
    error InsufficientBalance(uint256 available, uint256 required);

    // ---------------------------------------------------------------------
    // Initialization / Upgradeability
    // ---------------------------------------------------------------------

    /**
     * @notice Initialize the upgradeable vault
     * @param _owner Owner address
     * @param _blockHeaderRequester Address of BlockHeaderRequester
     */
    function initialize(
        address _owner,
        address _blockHeaderRequester
    ) external initializer {
        __Ownable_init(_owner);
        __Pausable_init();
        __ReentrancyGuard_init();
        __UUPSUpgradeable_init();

        blockHeaderRequester = BlockHeaderRequester(_blockHeaderRequester);
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}

    // ---------------------------------------------------------------------
    // Views (IPaymasterVault)
    // ---------------------------------------------------------------------

    function isTokenSupported(IERC20 token) external view override returns (bool supported) {
        return _assetConfigs[token].enabled;
    }

    function getTokenConfig(IERC20 token) external view override returns (
        uint256 minAmount,
        uint256 maxAmount,
        bool enabled
    ) {
        RemoteTypes.AssetConfig memory cfg = _assetConfigs[token];
        return (uint256(cfg.minAmount), uint256(cfg.maxAmount), cfg.enabled);
    }

    function getTotalDeposited(IERC20 token) external view override returns (uint256 totalDeposited) {
        return _totalDeposited[token];
    }

    function getDeposit(uint256 depositId) external view override returns (
        address depositor,
        address token,
        uint256 amount,
        address recipient,
        uint256 blockNumber,
        uint256 timestamp
    ) {
        RemoteTypes.DepositData storage d = _deposits[depositId];
        return (d.depositor, address(d.token), d.amount, d.recipient, d.blockNumber, d.timestamp);
    }

    function depositsArePaused() external view override returns (bool paused_) {
        return paused();
    }

    // ---------------------------------------------------------------------
    // Admin: Asset configuration (CRUD)
    // ---------------------------------------------------------------------

    /**
     * @notice Add or update a supported token configuration
     * @dev Validates using RemoteTypes.validateAssetConfig()
     */
    function setTokenConfig(IERC20 token, RemoteTypes.AssetConfig calldata cfg) external onlyOwner {
        // Validate config (reverts on invalid)
        RemoteTypes.validateAssetConfig(cfg);

        bool existed = _assetConfigs[token].minAmount != 0 || _assetConfigs[token].maxAmount != 0 || _assetConfigs[token].enabled;
        _assetConfigs[token] = cfg;

        if (existed) {
            emit TokenConfigUpdated(address(token), uint256(cfg.minAmount), uint256(cfg.maxAmount), cfg.enabled);
        } else {
            emit TokenAdded(address(token), uint256(cfg.minAmount), uint256(cfg.maxAmount));
            if (!cfg.enabled) {
                // Immediately follow with updated event if initially disabled
                emit TokenConfigUpdated(address(token), uint256(cfg.minAmount), uint256(cfg.maxAmount), false);
            }
        }
    }

    /**
     * @notice Enable or disable deposits for a token without changing amounts
     */
    function setTokenEnabled(IERC20 token, bool enabled) external onlyOwner {
        RemoteTypes.AssetConfig memory cfg = _assetConfigs[token];
        require(
            cfg.minAmount != 0 || cfg.maxAmount != 0 || cfg.enabled,
            UnsupportedToken()
        );
        _assetConfigs[token].enabled = enabled;
        emit TokenConfigUpdated(address(token), uint256(cfg.minAmount), uint256(cfg.maxAmount), enabled);
    }

    // ---------------------------------------------------------------------
    // Admin: Circuit breaker controls (per token)
    // ---------------------------------------------------------------------
    function setTokenDailyLimit(IERC20 token, uint128 newLimit) external onlyOwner {
        RemoteTypes.CircuitBreaker storage br = _tokenCircuitBreaker[token];
        // If this is the first time configuring, seed lastResetDay
        if (br.lastResetDay == 0) {
            br.lastResetDay = uint32(block.timestamp / 1 days);
        }
        br.dailyLimit = newLimit;
    }

    function setTokenCircuitBreakerEnabled(IERC20 token, bool enabled) external onlyOwner {
        RemoteTypes.CircuitBreaker storage br = _tokenCircuitBreaker[token];
        if (br.lastResetDay == 0) {
            br.lastResetDay = uint32(block.timestamp / 1 days);
        }
        br.enabled = enabled;
    }

    function getTokenCircuitBreaker(IERC20 token) external view returns (RemoteTypes.CircuitBreaker memory) {
        return _tokenCircuitBreaker[token];
    }

    // ---------------------------------------------------------------------
    // Pausing (IPaymasterVault)
    // ---------------------------------------------------------------------
    function pauseDeposits() external override onlyOwner {
        _pause();
        emit DepositsPaused(msg.sender);
    }

    function unpauseDeposits() external override onlyOwner {
        _unpause();
        emit DepositsUnpaused(msg.sender);
    }

    // ---------------------------------------------------------------------
    // Core: Deposit
    // ---------------------------------------------------------------------

    /**
     * @inheritdoc IPaymasterVault
     */
    function deposit(
        IERC20 token,
        uint256 amount,
        address recipient
    ) external override nonReentrant whenNotPaused returns (uint256 depositId) {
        require(recipient != address(0), InvalidRecipient());

        // Validate token support and bounds
        RemoteTypes.AssetConfig memory cfg = _assetConfigs[token];
        require(cfg.enabled, UnsupportedToken());
        require(amount >= uint256(cfg.minAmount), AmountBelowMinimum());
        require(amount <= uint256(cfg.maxAmount), AmountAboveMaximum());

        // Enforce circuit breaker (daily limit) per token
        RemoteTypes.CircuitBreaker memory br = _tokenCircuitBreaker[token];
        require(!RemoteTypes.shouldTriggerCircuitBreaker(br, uint128(amount)), CircuitBreakerTriggered());

        // Effects: compute identifiers and update accounting BEFORE external calls
        uint256 userNonce = _nonces[msg.sender];
        _nonces[msg.sender] = userNonce + 1;

        uint256 currentBlock = block.number;
        depositId = RemoteTypes.generateDepositId(msg.sender, token, amount, userNonce, currentBlock);

        _deposits[depositId] = RemoteTypes.DepositData({
            sourceChainId: uint32(block.chainid),
            depositor: msg.sender,
            token: token,
            amount: amount,
            recipient: recipient,
            blockNumber: currentBlock,
            timestamp: block.timestamp,
            nonce: userNonce,
            minRoseAmount: 0
        });

        // Update aggregate totals and circuit breaker counters
        _totalDeposited[token] += amount;
        // Update per-token breaker (memory -> storage)
        br = RemoteTypes.updateCircuitBreaker(br, uint128(amount));
        _tokenCircuitBreaker[token] = br;

        // Interactions: pull funds from user
        token.safeTransferFrom(msg.sender, address(this), amount);

        // Emit canonical interface event for indexing/reporting
        emit TokenDeposited(depositId, msg.sender, address(token), amount, recipient, currentBlock);

        // Hashi-friendly minimal event
        bytes32 paymentId = _computeContextPaymentId(address(this), currentBlock, depositId);
        emit PaymentInitiated(msg.sender, recipient, address(token), amount, paymentId);

        // Request block header for the current block to be available in ShoyuBashi
        // Non-critical: ignore if already requested
        try blockHeaderRequester.requestBlockHeader(block.chainid, currentBlock, paymentId) {
            // no-op; BlockHeaderRequester emits BlockHeaderRequested
        } catch {
            // Already requested or requester reverted; deposit remains valid
        }

        return depositId;
    }

    /**
     * @notice Owner withdrawal of accumulated ERC20 tokens to treasury
     * @dev nonReentrant to guard against ERC777-style callbacks
     */
    function withdrawToken(
        IERC20 token,
        address to,
        uint256 amount
    ) external override onlyOwner nonReentrant {
        require(to != address(0), ZeroAddress());
        require(amount != 0, InvalidAmount());
        uint256 bal = token.balanceOf(address(this));
        require(amount <= bal, InsufficientBalance(bal, amount));
        token.safeTransfer(to, amount);
        emit TokenWithdrawn(address(token), to, amount, msg.sender);
    }

    // ---------------------------------------------------------------------
    // Utilities
    // ---------------------------------------------------------------------

    /**
     * @notice Deterministic paymentId derivation used across the system (Hashi-compatible).
     * @dev Off-chain systems compute this using log metadata. Provided here for reference/testing.
     */
    function derivePaymentId(
        uint256 chainId,
        address vault,
        uint256 blockNumber,
        uint256 txIndex,
        uint256 logIndex
    ) public pure returns (bytes32) {
        return keccak256(abi.encode(chainId, vault, blockNumber, txIndex, logIndex));
    }

    function _computeContextPaymentId(
        address vault,
        uint256 blockNumber,
        uint256 depositId
    ) internal view returns (bytes32) {
        // Context identifier for correlating header requests; not used for on-chain proofing
        return keccak256(abi.encode(block.chainid, vault, blockNumber, depositId));
    }
}
