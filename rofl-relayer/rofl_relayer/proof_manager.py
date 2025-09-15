"""
Proof generation manager for ROFL Relayer.

This module handles the generation and submission of cryptographic proofs
for cross-chain message verification using the Hashi protocol format.
"""

import logging
from typing import TYPE_CHECKING, Any

import rlp
from eth_typing import HexStr
from trie import HexaryTrie
from web3 import Web3
from web3.types import TxParams, TxReceipt, Wei

from .models import PingEvent
from .utils.blockchain_encoder import BlockchainEncoder

if TYPE_CHECKING:
    from .utils.contract_utility import ContractUtility
    from .utils.rofl_utility import ROFLUtility

logger = logging.getLogger(__name__)


class ProofManager:
    """Handles proof generation and submission for cross-chain messages."""

    def __init__(
        self,
        w3_source: Web3,
        contract_util: "ContractUtility",
        rofl_util: "ROFLUtility | None" = None,
    ):
        """
        Initialize the ProofManager.

        Args:
            w3_source: Web3 instance for the source chain
            contract_util: Utility for contract interactions
            rofl_util: ROFL utility for transaction submission (optional)
        """
        self.w3_source = w3_source
        self.contract_util = contract_util
        self.rofl_util = rofl_util

    def _get_transaction_local_index(self, ping_event: PingEvent) -> int:
        """
        Find the transaction-local index for a specific Ping event.

        This matches the event by its content rather than using global log index.
        For Ping events:
        - Event signature: Ping(address,uint256)
        - Topics[0]: keccak256("Ping(address,uint256)")
        - Topics[1]: indexed sender address (padded to 32 bytes)
        - Topics[2]: indexed block number (as 32 bytes)

        Args:
            ping_event: The PingEvent object containing tx_hash, sender, and block_number

        Returns:
            Transaction-local index (position within transaction's logs)
        """
        receipt = self.w3_source.eth.get_transaction_receipt(HexStr(ping_event.tx_hash))
        if not receipt or "logs" not in receipt:
            logger.warning(f"No logs found in transaction {ping_event.tx_hash}")
            return 0

        # Calculate Ping event signature hash
        ping_topic = Web3.keccak(text="Ping(address,uint256)")

        # Prepare sender address (pad to 32 bytes)
        sender_bytes = Web3.to_bytes(hexstr=ping_event.sender)
        sender_topic = sender_bytes.rjust(32, b"\0")

        # Prepare block number (as 32 bytes)
        block_topic = ping_event.block_number.to_bytes(32, "big")

        # Find matching Ping event in transaction logs
        for i, log in enumerate(receipt["logs"]):
            topics = log.get("topics", [])
            if (
                len(topics) >= 3
                and topics[0] == ping_topic
                and topics[1] == sender_topic
                and topics[2] == block_topic
            ):
                logger.info(f"Found Ping event at transaction-local index {i}")
                return i

        # If not found (shouldn't happen), default to 0
        logger.warning(
            "Ping event not found in transaction logs, defaulting to index 0"
        )
        return 0

    async def generate_proof(self, ping_event: PingEvent) -> list[Any]:
        """
        Generate Hashi-format proof for a Ping event.

        Uses eth_getBlockReceipts for efficient batch receipt fetching when available.

        Args:
            ping_event: The PingEvent object containing all event data

        Returns:
            8-element array matching TypeScript format for Hashi proof

        Raises:
            ValueError: If receipt or block not found, or proof generation fails
        """
        # Calculate transaction-local log index from event content
        log_index = self._get_transaction_local_index(ping_event)
        logger.info(
            f"Generating proof for tx {ping_event.tx_hash}, transaction-local log index {log_index}"
        )

        # 1. Fetch receipt and block
        receipt = self.w3_source.eth.get_transaction_receipt(HexStr(ping_event.tx_hash))
        if not receipt:
            raise ValueError(f"Transaction receipt not found for {ping_event.tx_hash}")

        block_number = receipt["blockNumber"]
        block = self.w3_source.eth.get_block(block_number, full_transactions=True)
        if not block:
            raise ValueError(f"Block not found for block number {block_number}")

        logger.info(
            f"Processing block {block_number}, tx index {receipt['transactionIndex']}"
        )

        # 2. Get all receipts in block
        receipts = self._get_block_receipts(block_number)

        logger.info(f"Fetched {len(receipts)} receipts from block")

        # 3. RLP encode all receipts and build trie
        trie = HexaryTrie({})

        for _idx, rec in enumerate(receipts):
            # Encode transaction index as trie key
            tx_index = rec["transactionIndex"]
            key = BlockchainEncoder.encode_transaction_index(tx_index)

            # Encode the receipt
            encoded_receipt = BlockchainEncoder.encode_receipt(rec)

            # Put in trie
            trie[key] = encoded_receipt

        # 4. Verify trie root matches block's receiptsRoot
        calculated_root = Web3.to_hex(trie.root_hash)
        block_receipts_root = Web3.to_hex(block["receiptsRoot"])

        if calculated_root != block_receipts_root:
            raise ValueError(
                f"Trie root mismatch! Calculated: {calculated_root}, Block: {block_receipts_root}"
            )

        # 5. Generate proof for target receipt
        tx_index = receipt["transactionIndex"]
        receipt_key = BlockchainEncoder.encode_transaction_index(tx_index)
        proof_nodes = trie.get_proof(receipt_key)

        # Convert proof nodes to hex strings
        merkle_proof = [Web3.to_hex(rlp.encode(node)) for node in proof_nodes]

        # 6. Encode block header
        encoded_block_header = BlockchainEncoder.encode_block_header(block)

        # 7. Get chain ID
        chain_id = int(self.w3_source.eth.chain_id)

        # 8. Create proof structure for Hashi
        proof = [
            chain_id,  # chainId
            block_number,  # blockNumber
            encoded_block_header,  # encodedBlockHeader
            0,  # ancestralBlockNumber (not used in MVP)
            [],  # ancestralBlockHeaders (not used in MVP)
            merkle_proof,  # merkleProof
            Web3.to_hex(receipt_key),  # transactionIndex (RLP encoded)
            log_index,  # logIndex
        ]

        logger.info(
            f"Proof generated successfully with {len(merkle_proof)} merkle nodes"
        )
        return proof

    async def submit_proof(self, proof: list[Any], receiver_address: str) -> str:
        """
        Submit proof to PingReceiver contract.

        Args:
            proof: The generated proof array
            receiver_address: Address of the PingReceiver contract

        Returns:
            Transaction hash of the submission
        """
        logger.info(f"Submitting proof to PingReceiver at {receiver_address}")

        abi = self.contract_util.get_contract_abi("PingReceiver")
        contract = self.contract_util.w3.eth.contract(
            address=Web3.to_checksum_address(receiver_address), abi=abi
        )

        # Convert proof array to struct format expected by PingReceiver
        receipt_proof_struct = {
            "chainId": proof[0],
            "blockNumber": proof[1],
            "blockHeader": proof[2],
            "ancestralBlockNumber": proof[3],
            "ancestralBlockHeaders": proof[4],
            "receiptProof": proof[5],  # This is the merkleProof array
            "transactionIndex": proof[6],
            "logIndex": proof[7],
        }

        logger.info(
            f"Proof formatted for ReceiptProof struct with {len(proof[5])} merkle proof elements"
        )

        if self.rofl_util:
            # ROFL mode: build transaction for rofl_util
            tx_params: TxParams = {
                "from": "0x0000000000000000000000000000000000000000",  # ROFL will override
                "gas": 3000000,
                "gasPrice": self.contract_util.w3.eth.gas_price,
                "value": Wei(0),
            }
            tx_data = contract.functions.receivePing(
                receipt_proof_struct
            ).build_transaction(tx_params)
            success = await self.rofl_util.submit_tx(tx_data)
            if success:
                logger.info("Proof submitted successfully via ROFL")
                # Return a success indicator since ROFL doesn't provide tx hash
                return "ROFL_SUBMITTED"
            else:
                logger.error("Failed to submit proof via ROFL")
                raise Exception("ROFL submission failed")
        else:
            # Local mode
            tx_hash = contract.functions.receivePing(receipt_proof_struct).transact(
                {"gas": 3000000, "gasPrice": self.contract_util.w3.eth.gas_price}
            )
            logger.info(f"Proof submitted locally: {Web3.to_hex(tx_hash)}")
            return Web3.to_hex(tx_hash)

    async def process_ping_event(
        self, ping_event: PingEvent, receiver_address: str
    ) -> str:
        """
        Complete flow: generate and submit proof for a ping event.

        Args:
            ping_event: The PingEvent object containing tx_hash, sender, and block_number
            receiver_address: Address of the PingReceiver contract

        Returns:
            Transaction hash of the proof submission
        """
        logger.info(
            f"Processing ping event with tx_hash={ping_event.tx_hash}, sender={ping_event.sender}, block={ping_event.block_number}"
        )
        proof = await self.generate_proof(ping_event)
        return await self.submit_proof(proof, receiver_address)

    def _get_block_receipts(self, block_number: int) -> list[TxReceipt]:
        """
        Get all receipts for a block using eth_getBlockReceipts.

        Args:
            block_number: The block number

        Returns:
            List of transaction receipts

        Raises:
            ValueError: If block receipts cannot be fetched
        """
        try:
            receipts = self.w3_source.eth.get_block_receipts(block_number)
        except Exception as e:
            logger.error(f"Failed to fetch receipts for block {block_number}: {e}")
            raise ValueError(
                f"Failed to fetch receipts for block {block_number}"
            ) from e

        if receipts is None:
            logger.error(f"get_block_receipts returned None for block {block_number}")
            raise ValueError(f"Block receipts unavailable for block {block_number}")

        # Empty receipts list is valid (e.g., empty blocks) but worth logging
        if not receipts:
            logger.warning(f"Block {block_number} contains no receipts (empty block)")
        else:
            logger.info(f"Fetched {len(receipts)} receipts from block {block_number}")

        return receipts
