// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import { Initializable } from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import { UUPSUpgradeable } from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import { PausableUpgradeable } from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import { ReentrancyGuardUpgradeable } from "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";

import { RLPReader } from "@eth-optimism/contracts-bedrock/src/libraries/rlp/RLPReader.sol";

import { HashiProverUpgradeable } from "../hashi/prover/HashiProverUpgradeable.sol";
import { ReceiptProof } from "../hashi/prover/HashiProverStructs.sol";

import { IROFLPriceOracle } from "./interfaces/IROFLPriceOracle.sol";
import { SapphireTypes } from "./libraries/SapphireTypes.sol";

/**
 * @title CrossChainPaymaster
 * @notice Sapphire contract that verifies remote PaymentInitiated events via Hashi and distributes ROSE
 * @dev UUPS upgradeable. Uses ROFL price oracle for conversions. Duplicate prevention via paymentId.
 */
contract CrossChainPaymaster is
    Initializable,
    UUPSUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    HashiProverUpgradeable
{
    using RLPReader for RLPReader.RLPItem;
    using RLPReader for bytes;

    // ---------------------------------------------------------------------
    // Events (keep minimal on Sapphire for privacy)
    // ---------------------------------------------------------------------
    event PaymentProcessed(bytes32 indexed paymentId, uint256 roseAmount);
    event OperatorUpdated(address indexed oldOperator, address indexed newOperator);
    event PriceOracleUpdated(address indexed oldOracle, address indexed newOracle);
    event ChainConfigUpdated(uint256 indexed chainId, SapphireTypes.ChainConfig config);
    event VaultAuthorizationUpdated(uint256 indexed chainId, address indexed vault, bool authorized);
    event DistributionLimitsUpdated(
        uint128 dailyLimit,
        uint128 perTxLimit,
        bool enabled
    );

    // ---------------------------------------------------------------------
    // Constants
    // ---------------------------------------------------------------------
    bytes32 internal constant PAYMENT_INITIATED_TOPIC = keccak256(
        abi.encodePacked(
            "PaymentInitiated(address,address,address,uint256,bytes32)"
        )
    );

    // ---------------------------------------------------------------------
    // Storage
    // ---------------------------------------------------------------------

    // Price oracle for conversions
    IROFLPriceOracle public priceOracle;

    // ROFL operator (allowed to trigger processing, pause, config)
    address public roflOperator;

    // Duplicate prevention mapping (paymentId => processed)
    mapping(bytes32 => bool) public processedPayments;

    // Chain configuration (chainId => config)
    mapping(uint256 => SapphireTypes.ChainConfig) public chainConfigs;

    // Authorized source vaults per chain
    mapping(uint256 => mapping(address => bool)) public isAuthorizedVault;

    // Distribution limits and counters
    SapphireTypes.DistributionLimits public limits;

    // ---------------------------------------------------------------------
    // Errors
    // ---------------------------------------------------------------------
    error NotOperatorOrOwner();
    error InvalidOracle();
    error ChainDisabled(uint256 chainId);
    error VaultNotAuthorized(uint256 chainId, address vault);
    error InvalidEvent();
    error DuplicatePayment(bytes32 paymentId);
    error DistributionLimitExceeded();
    error TransferFailed();

    // ---------------------------------------------------------------------
    // Initialization / Upgradeability
    // ---------------------------------------------------------------------
    function initialize(
        address _owner,
        address _operator,
        address _priceOracle,
        address _shoyuBashi,
        SapphireTypes.DistributionLimits memory _limits
    ) external initializer {
        // Initialize parents in linearized order: Reentrancy -> HashiProver -> (others)
        __ReentrancyGuard_init();
        __HashiProverUpgradeable_init(_shoyuBashi);
        __Pausable_init();
        __UUPSUpgradeable_init();

        if (_priceOracle == address(0)) revert InvalidOracle();
        priceOracle = IROFLPriceOracle(_priceOracle);
        roflOperator = _operator;
        limits = _limits;

        // Transfer ownership to requested owner if different
        if (_owner != owner()) {
            _transferOwnership(_owner);
        }
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}

    // ---------------------------------------------------------------------
    // Modifiers
    // ---------------------------------------------------------------------
    modifier onlyOperatorOrOwner() {
        if (msg.sender != roflOperator && msg.sender != owner()) revert NotOperatorOrOwner();
        _;
    }

    // ---------------------------------------------------------------------
    // Admin
    // ---------------------------------------------------------------------
    function setOperator(address _operator) external onlyOwner {
        emit OperatorUpdated(roflOperator, _operator);
        roflOperator = _operator;
    }

    function setPriceOracle(address _oracle) external onlyOwner {
        if (_oracle == address(0)) revert InvalidOracle();
        emit PriceOracleUpdated(address(priceOracle), _oracle);
        priceOracle = IROFLPriceOracle(_oracle);
    }

    function setChainConfig(uint256 chainId, SapphireTypes.ChainConfig calldata config) external onlyOwner {
        chainConfigs[chainId] = config;
        emit ChainConfigUpdated(chainId, config);
    }

    function setVaultAuthorization(uint256 chainId, address vault, bool authorized) external onlyOwner {
        isAuthorizedVault[chainId][vault] = authorized;
        emit VaultAuthorizationUpdated(chainId, vault, authorized);
    }

    function setDistributionLimits(
        uint128 dailyLimit,
        uint128 perTxLimit,
        bool enabled
    ) external onlyOwner {
        limits.dailyLimit = dailyLimit;
        limits.perTxLimit = perTxLimit;
        limits.enabled = enabled;
        // reset window if changing config
        limits.lastResetDay = uint32(block.timestamp / 1 days);
        limits.currentDaily = 0;
        emit DistributionLimitsUpdated(dailyLimit, perTxLimit, enabled);
    }

    function pause() external onlyOperatorOrOwner {
        _pause();
    }

    function unpause() external onlyOperatorOrOwner {
        _unpause();
    }

    // ---------------------------------------------------------------------
    // Core: Verify proof and distribute ROSE
    // ---------------------------------------------------------------------

    /**
     * @notice Verifies a PaymentInitiated event via Hashi and distributes ROSE to the recipient.
     * @param proof Hashi receipt proof (see ReceiptProof struct)
     * @dev Permissionless; security enforced by proof verification, chain/vault config, limits, and replay protection.
     */
    function processPayment(ReceiptProof calldata proof) external nonReentrant whenNotPaused {
        _processPayment(proof);
    }

    function _processPayment(ReceiptProof calldata proof) internal {
        // Ensure source chain is enabled
        SapphireTypes.ChainConfig memory cfg = chainConfigs[proof.chainId];
        if (!cfg.enabled) revert ChainDisabled(proof.chainId);

        // Verify event via Hashi (returns RLP-encoded Log: [address, topics[], data])
        bytes memory logEntry = verifyForeignEvent(proof);

        // Decode and validate event
        (
            address vault,
            address payer,
            address recipient,
            address token,
            uint256 amount,
            bytes32 eventPaymentId
        ) = _decodePaymentInitiated(logEntry);

        // Vault must be authorized for this chain
        if (!isAuthorizedVault[proof.chainId][vault]) revert VaultNotAuthorized(proof.chainId, vault);

        // Compute canonical paymentId from proof metadata
        uint256 txIndex = _decodeRlpUint(proof.transactionIndex);
        bytes32 paymentId = keccak256(abi.encode(
            proof.chainId,
            vault,
            proof.blockNumber,
            txIndex,
            proof.logIndex
        ));

        // Duplicate prevention
        if (processedPayments[paymentId]) revert DuplicatePayment(paymentId);

        // Convert to ROSE using oracle; downstream oracle handles decimals and staleness policies
        uint256 roseAmount = priceOracle.convertToRose(token, amount);

        // Enforce limits
        if (SapphireTypes.wouldExceedLimits(limits, uint128(roseAmount))) revert DistributionLimitExceeded();

        // Effects
        processedPayments[paymentId] = true;
        limits = SapphireTypes.updateDistributionLimits(limits, uint128(roseAmount));

        // Interactions: send ROSE
        (bool ok, ) = payable(recipient).call{value: roseAmount}("");
        if (!ok) revert TransferFailed();

        emit PaymentProcessed(paymentId, roseAmount);

        // Silence state variable warnings
        (payer, eventPaymentId);
    }

    // ---------------------------------------------------------------------
    // Views / Helpers
    // ---------------------------------------------------------------------

    function calculateRoseAmount(address token, uint256 tokenAmount) external view returns (uint256) {
        return priceOracle.convertToRose(token, tokenAmount);
    }

    function isPaymentProcessed(bytes32 paymentId) external view returns (bool) {
        return processedPayments[paymentId];
    }

    // Decode PaymentInitiated log: [address, [topics...], data]
    function _decodePaymentInitiated(bytes memory logEntry) internal pure returns (
        address vault,
        address payer,
        address recipient,
        address token,
        uint256 amount,
        bytes32 paymentId
    ) {
        RLPReader.RLPItem[] memory fields = logEntry.toRLPItem().readList();
        if (fields.length != 3) revert InvalidEvent();

        // 0: address
        vault = address(bytes20(fields[0].readBytes()));

        // 1: topics[]
        RLPReader.RLPItem[] memory topics = fields[1].readList();
        if (topics.length != 4) revert InvalidEvent(); // sig + 3 indexed
        bytes32 sig = bytes32(topics[0].readBytes());
        if (sig != PAYMENT_INITIATED_TOPIC) revert InvalidEvent();
        payer = address(uint160(uint256(bytes32(topics[1].readBytes()))));
        recipient = address(uint160(uint256(bytes32(topics[2].readBytes()))));
        token = address(uint160(uint256(bytes32(topics[3].readBytes()))));

        // 2: data (abi.encode(amount, paymentId))
        bytes memory data = fields[2].readBytes();
        if (data.length == 0) revert InvalidEvent();
        (amount, paymentId) = abi.decode(data, (uint256, bytes32));
    }

    // Decode RLP-encoded uint to uint256
    function _decodeRlpUint(bytes memory rlp) internal pure returns (uint256) {
        bytes memory b = rlp.toRLPItem().readBytes();
        uint256 number;
        for (uint256 i = 0; i < b.length; i++) {
            number = number + uint256(uint8(b[i])) * (2 ** (8 * (b.length - (i + 1))));
        }
        return number;
    }

    // Accept ROSE funding
    receive() external payable {}
}
