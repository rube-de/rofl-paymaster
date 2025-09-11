// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import { ReceiptProof } from "../hashi/prover/HashiProverStructs.sol";

/**
 * @title IPingReceiver
 * @notice Interface for simple cross-chain ping receiver
 * @dev Verifies that ping events occurred on other chains using cryptographic proofs
 */
interface IPingReceiver {
    
    /**
     * @notice Information about a received ping
     * @param received Whether ping was received
     * @param originalSender Address that sent the ping on source chain
     * @param originalBlockNumber Block number where ping occurred on source chain
     */
    struct ReceivedPing {
        bool received;
        address originalSender;
        uint256 originalBlockNumber;
    }
    
    /**
     * @notice Emitted when a ping is successfully received and verified
     * @param sourceChainId Chain ID where ping originally occurred
     * @param pingId Unique ping identifier
     * @param originalSender Address that sent the ping on source chain
     * @param originalBlockNumber Block number where ping occurred on source chain
     */
    event PingReceived(
        uint256 indexed sourceChainId,
        bytes32 indexed pingId,
        address indexed originalSender,
        uint256 originalBlockNumber
    );
    
    /**
     * @notice Emitted after ping verification attempt
     * @param pingId Unique ping identifier
     * @param success Whether verification succeeded
     * @param reason Description of result
     */
    event PingVerified(
        bytes32 indexed pingId,
        bool success,
        string reason
    );
    
    error PingAlreadyReceived(bytes32 pingId);
    error InvalidProof();
    error InvalidEventFormat();
    
    /**
     * @notice Receive and verify a cross-chain ping
     * @param proof Receipt proof containing transaction and log data
     * @dev Anyone can call this with a valid proof - security comes from cryptographic verification
     */
    function receivePing(ReceiptProof calldata proof) external;
    
    /**
     * @notice Check if ping has been received
     * @param pingId Ping ID to check
     * @return received Whether ping was received
     * @return originalSender Original sender address
     * @return originalBlockNumber Block where ping occurred
     */
    function getPingStatus(bytes32 pingId) external view returns (
        bool received,
        address originalSender,
        uint256 originalBlockNumber
    );
}