// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import { HashiProver } from "./hashi/prover/HashiProver.sol";
import { ReceiptProof } from "./hashi/prover/HashiProverStructs.sol";
import { RLPReader } from "@eth-optimism/contracts-bedrock/src/libraries/rlp/RLPReader.sol";
import "./interfaces/IPingReceiver.sol";

/**
 * @title PingReceiver
 * @notice Contract for receiving and verifying simple cross-chain pings on Oasis Sapphire
 * @dev Uses Hashi's cryptographic verification to prove ping events occurred on other chains
 */
contract PingReceiver is IPingReceiver, HashiProver {
    using RLPReader for RLPReader.RLPItem;
    using RLPReader for bytes;
    
    mapping(bytes32 => ReceivedPing) public receivedPings;
    
    constructor(address _shoyuBashi) HashiProver(_shoyuBashi) {}
    
    /**
     * @notice Receive and verify a cross-chain ping
     * @param proof Receipt proof containing transaction and log data
     * @dev Anyone can call this function with a valid proof - security comes from cryptographic verification
     */
    function receivePing(ReceiptProof calldata proof) external {
        // Verify the foreign ping event using Hashi prover
        bytes memory eventData = verifyForeignEvent(proof);
        
        // Decode the minimal ping event
        (address sender, uint256 blockNumber) = decodeEventData(eventData);
        
        // Generate ping ID from the verified event data
        bytes32 pingId = keccak256(abi.encode(proof.chainId, sender, blockNumber));
        
        // Check if ping already received
        if (receivedPings[pingId].received) {
            revert PingAlreadyReceived(pingId);
        }
        
        // Store received ping
        receivedPings[pingId] = ReceivedPing({
            received: true,
            originalSender: sender,
            originalBlockNumber: blockNumber
        });
        
        emit PingReceived(proof.chainId, pingId, sender, blockNumber);
        emit PingVerified(pingId, true, "Ping successfully verified");
    }
    
    /**
     * @notice Decode RLP-encoded ping event data
     * @param eventData Raw RLP-encoded event data from proof verification
     * @return sender Address that sent the ping
     * @return blockNumber Block number where ping occurred
     * @dev Expects Ping event with 2 indexed parameters, 0 data parameters
     */
    function decodeEventData(bytes memory eventData) internal pure returns (
        address sender,
        uint256 blockNumber
    ) {
        // Decode the event data as a list of event fields
        RLPReader.RLPItem[] memory eventFields = eventData.toRLPItem().readList();
        if (eventFields.length != 3) revert InvalidEventFormat(); // address, topics, data
        
        // Extract topics (indexed parameters)
        RLPReader.RLPItem[] memory topics = eventFields[1].readList();
        if (topics.length != 3) revert InvalidEventFormat(); // event signature + 2 indexed params
        
        // Decode indexed parameters from topics
        sender = address(bytes20(topics[1].readBytes()));
        blockNumber = uint256(bytes32(topics[2].readBytes()));
        
        // No data field to decode - everything is indexed
    }
    
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
    ) {
        ReceivedPing memory ping = receivedPings[pingId];
        return (ping.received, ping.originalSender, ping.originalBlockNumber);
    }
}