// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title IPingSender
 * @notice Interface for simple cross-chain ping sender
 * @dev Emits minimal ping events that can be proven on other chains
 */
interface IPingSender {
    
    /**
     * @notice Emitted when a ping occurs
     * @param sender Address that sent the ping
     * @param blockNumber Block number where ping occurred
     */
    event Ping(
        address indexed sender,
        uint256 indexed blockNumber
    );
    
    /**
     * @notice Emitted when block header is requested for verification
     * @param sourceChainId Chain ID where ping occurred
     * @param blockNumber Block number to get header for
     * @param pingId Unique ping identifier
     */
    event HeaderRequested(
        uint256 indexed sourceChainId,
        uint256 indexed blockNumber,
        bytes32 indexed pingId
    );
    
    /**
     * @notice Send a simple ping
     * @return pingId Unique identifier for this ping
     */
    function ping() external returns (bytes32 pingId);
    
    /**
     * @notice Generate unique ping ID
     * @param sourceChainId Source chain ID
     * @param sender Ping sender address
     * @param blockNumber Block where ping occurred
     * @return pingId Unique ping identifier
     */
    function generatePingId(
        uint256 sourceChainId,
        address sender,
        uint256 blockNumber
    ) external pure returns (bytes32 pingId);
}