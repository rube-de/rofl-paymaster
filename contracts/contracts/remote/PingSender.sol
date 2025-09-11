// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "./BlockHeaderRequester.sol";
import "./interfaces/IPingSender.sol";

/**
 * @title PingSender
 * @notice Contract for sending simple cross-chain pings
 * @dev Emits minimal ping events that can be proven on other chains using Hashi
 */
contract PingSender is IPingSender {
    
    BlockHeaderRequester public immutable blockHeaderRequester;
    uint256 public immutable SOURCE_CHAIN_ID;
    
    constructor(address _blockHeaderRequester, uint256 _sourceChainId) {
        blockHeaderRequester = BlockHeaderRequester(_blockHeaderRequester);
        SOURCE_CHAIN_ID = _sourceChainId;
    }
    
    /**
     * @notice Send a simple ping
     * @return pingId Unique identifier for this ping
     * @dev Emits a minimal event that can be cryptographically proven on other chains
     */
    function ping() external returns (bytes32 pingId) {
        uint256 currentBlock = block.number;
        
        // Generate deterministic ping ID
        pingId = generatePingId(SOURCE_CHAIN_ID, msg.sender, currentBlock);
        
        // Emit minimal ping event
        emit Ping(msg.sender, currentBlock);
        
        // Request block header for verification on target chain
        try blockHeaderRequester.requestBlockHeader(
            SOURCE_CHAIN_ID,
            currentBlock,
            pingId
        ) {
            emit HeaderRequested(SOURCE_CHAIN_ID, currentBlock, pingId);
        } catch {
            // Header already requested - no problem
        }
    }
    
    /**
     * @notice Generate unique ping ID
     * @param sourceChainId Source chain ID
     * @param sender Ping sender address
     * @param blockNumber Block where ping occurred
     * @return pingId Unique ping identifier
     * @dev Uses deterministic formula: keccak256(sourceChainId, sender, blockNumber)
     */
    function generatePingId(
        uint256 sourceChainId,
        address sender,
        uint256 blockNumber
    ) public pure returns (bytes32 pingId) {
        return keccak256(abi.encode(sourceChainId, sender, blockNumber));
    }
}