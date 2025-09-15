// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import { IROFLPriceOracle } from "./interfaces/IROFLPriceOracle.sol";

/**
 * @title MockROFLPriceOracle
 * @notice Mock oracle that always returns a 1:1 price (1e18) and converts token amounts to ROSE 1:1,
 *         adjusting only for decimals when provided.
 * @dev Minimal implementation to satisfy the IROFLPriceOracle interface for testing.
 */
contract MockROFLPriceOracle is IROFLPriceOracle {
    // Optional: allow setting token decimals for realistic conversions
    mapping(address => uint8) private _tokenDecimals;

    // Config (not used for pricing logic in mock)
    uint256 private _stalenessThreshold; // seconds
    uint256 private _minConfidence; // not used, but stored for completeness
    bool private _paused;

    // Constants
    uint256 internal constant ONE = 1e18; // 1 ROSE in 18 decimals

    // ---------------------------------------------------------------------
    // Views
    // ---------------------------------------------------------------------

    function getPrice(address /* token */) external view override returns (uint256 price, uint256 timestamp) {
        // Always return 1e18 and current timestamp as if updated now
        return (ONE, block.timestamp);
    }

    function convertToRose(address token, uint256 tokenAmount) external view override returns (uint256 roseAmount) {
        // 1 token == 1 ROSE, normalized to 18 decimals
        uint8 d = _getDecimals(token);
        if (d == 18) return tokenAmount;
        if (d < 18) return tokenAmount * (10 ** uint256(18 - d));
        // d > 18
        return tokenAmount / (10 ** uint256(d - 18));
    }

    function convertFromRose(address token, uint256 roseAmount) external view override returns (uint256 tokenAmount) {
        // Inverse of convertToRose for 1:1 pricing
        uint8 d = _getDecimals(token);
        if (d == 18) return roseAmount;
        if (d < 18) return roseAmount / (10 ** uint256(18 - d));
        // d > 18
        return roseAmount * (10 ** uint256(d - 18));
    }

    function isTokenSupported(address /* token */) external pure override returns (bool supported) {
        // In mock, all tokens are "supported"
        return true;
    }

    function isPriceStale(address /* token */) external pure override returns (bool stale) {
        // Never stale in mock
        return false;
    }

    function stalenessThreshold() external view override returns (uint256 threshold) {
        return _stalenessThreshold;
    }

    function getTokenDecimals(address token) external view override returns (uint8 decimals) {
        return _getDecimals(token);
    }

    function isPaused() external view override returns (bool paused) {
        return _paused;
    }

    // ---------------------------------------------------------------------
    // Admin-like methods (no-op for pricing, but stored/emitted for completeness)
    // ---------------------------------------------------------------------

    function updatePrice(address token, uint256 price, uint256 confidence) external override {
        // No-op for pricing in mock; emit event for observability
        emit PriceUpdated(token, price, block.timestamp, block.number, confidence);
    }

    function updatePrices(
        address[] calldata tokens,
        uint256[] calldata prices,
        uint256[] calldata confidences
    ) external override {
        require(tokens.length == prices.length && prices.length == confidences.length, "len mismatch");
        for (uint256 i = 0; i < tokens.length; i++) {
            emit PriceUpdated(tokens[i], prices[i], block.timestamp, block.number, confidences[i]);
        }
    }

    function pauseOracle() external override {
        _paused = true;
        emit OraclePauseStatusChanged(true, block.timestamp);
    }

    function unpauseOracle() external override {
        _paused = false;
        emit OraclePauseStatusChanged(false, block.timestamp);
    }

    function addTokenFeed(address token, uint256 initialPrice, uint8 decimals) external override {
        _tokenDecimals[token] = decimals;
        emit TokenFeedAdded(token, initialPrice, decimals);
    }

    function removeTokenFeed(address token) external override {
        delete _tokenDecimals[token];
        emit TokenFeedRemoved(token);
    }

    function updateOracleConfig(uint256 stalenessThreshold_, uint256 minConfidence_) external override {
        _stalenessThreshold = stalenessThreshold_;
        _minConfidence = minConfidence_;
        emit OracleConfigUpdated(stalenessThreshold_, minConfidence_);
    }

    // ---------------------------------------------------------------------
    // Internal helpers
    // ---------------------------------------------------------------------

    function _getDecimals(address token) internal view returns (uint8) {
        uint8 d = _tokenDecimals[token];
        return d == 0 ? 18 : d; // default to 18 if not explicitly set
    }
}

