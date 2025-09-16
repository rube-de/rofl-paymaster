"""Web3 utility functions and helpers."""

import asyncio
import time
from typing import Dict, List, Optional, Union, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass

from web3 import Web3, AsyncWeb3
from web3.types import (
    BlockData, TxData, TxReceipt, LogReceipt, FilterParams,
    Wei, HexBytes, ChecksumAddress
)
from web3.exceptions import Web3Exception, TransactionNotFound, BlockNotFound
from eth_account import Account
from eth_account.signers.local import LocalAccount

from .config import Web3Config
from .logging import get_logger


@dataclass
class GasEstimate:
    """Gas estimation result."""
    
    gas_limit: int
    gas_price: Wei
    max_fee_per_gas: Optional[Wei] = None
    max_priority_fee_per_gas: Optional[Wei] = None
    estimated_cost: Wei = Wei(0)
    is_eip1559: bool = False
    
    def __post_init__(self):
        """Calculate estimated cost."""
        if self.is_eip1559 and self.max_fee_per_gas:
            self.estimated_cost = Wei(self.gas_limit * self.max_fee_per_gas)
        else:
            self.estimated_cost = Wei(self.gas_limit * self.gas_price)


@dataclass
class TransactionStatus:
    """Transaction status information."""
    
    hash: HexBytes
    status: str  # pending, confirmed, failed, not_found
    block_number: Optional[int] = None
    confirmations: int = 0
    gas_used: Optional[int] = None
    effective_gas_price: Optional[Wei] = None
    receipt: Optional[TxReceipt] = None
    
    @property
    def is_confirmed(self) -> bool:
        """Check if transaction is confirmed."""
        return self.status == "confirmed"
    
    @property
    def is_failed(self) -> bool:
        """Check if transaction failed."""
        return self.status == "failed"


class Web3Helpers:
    """Web3 utility functions and helpers."""
    
    def __init__(self, web3: Web3, async_web3: AsyncWeb3, config: Web3Config):
        """Initialize Web3 helpers.
        
        Args:
            web3: Synchronous Web3 instance
            async_web3: Asynchronous Web3 instance
            config: Web3 configuration
        """
        self.web3 = web3
        self.async_web3 = async_web3
        self.config = config
        self.logger = get_logger("web3_helpers")
        
        # Cache for gas price data
        self._gas_price_cache: Optional[Tuple[float, GasEstimate]] = None
        self._gas_price_cache_ttl = 30.0  # 30 seconds
    
    # Account and Address Utilities
    
    def create_account(self) -> LocalAccount:
        """Create a new random account."""
        return Account.create()
    
    def account_from_private_key(self, private_key: str) -> LocalAccount:
        """Create account from private key.
        
        Args:
            private_key: Private key hex string
            
        Returns:
            LocalAccount instance
        """
        return Account.from_key(private_key)
    
    def is_valid_address(self, address: str) -> bool:
        """Check if address is valid Ethereum address.
        
        Args:
            address: Address to validate
            
        Returns:
            True if valid address
        """
        return Web3.is_address(address)
    
    def to_checksum_address(self, address: str) -> ChecksumAddress:
        """Convert address to checksum format.
        
        Args:
            address: Address to convert
            
        Returns:
            Checksummed address
        """
        return Web3.to_checksum_address(address)
    
    # Balance and Token Utilities
    
    async def get_balance(self, address: str, block: str = "latest") -> Wei:
        """Get ETH balance for address.
        
        Args:
            address: Address to check
            block: Block number or 'latest'
            
        Returns:
            Balance in Wei
        """
        return await self.async_web3.eth.get_balance(
            Web3.to_checksum_address(address), block
        )
    
    async def get_token_balance(
        self, 
        token_address: str, 
        holder_address: str,
        decimals: int = 18
    ) -> Decimal:
        """Get ERC20 token balance.
        
        Args:
            token_address: Token contract address
            holder_address: Token holder address
            decimals: Token decimals
            
        Returns:
            Token balance as Decimal
        """
        # ERC20 balanceOf function signature
        function_selector = Web3.keccak(text="balanceOf(address)")[:4]
        
        # Encode the holder address
        encoded_address = Web3.to_checksum_address(holder_address).lower().replace('0x', '').zfill(64)
        data = function_selector.hex() + encoded_address
        
        # Call the contract
        result = await self.async_web3.eth.call({
            "to": Web3.to_checksum_address(token_address),
            "data": data
        })
        
        # Decode result
        balance_wei = int(result.hex(), 16)
        return Decimal(balance_wei) / Decimal(10 ** decimals)
    
    # Block and Transaction Utilities
    
    async def get_latest_block(self, full_transactions: bool = False) -> BlockData:
        """Get latest block.
        
        Args:
            full_transactions: Include full transaction data
            
        Returns:
            Block data
        """
        return await self.async_web3.eth.get_block("latest", full_transactions)
    
    async def get_block(
        self, 
        block_identifier: Union[int, str], 
        full_transactions: bool = False
    ) -> Optional[BlockData]:
        """Get block by number or hash.
        
        Args:
            block_identifier: Block number or hash
            full_transactions: Include full transaction data
            
        Returns:
            Block data or None if not found
        """
        try:
            return await self.async_web3.eth.get_block(block_identifier, full_transactions)
        except BlockNotFound:
            return None
    
    async def get_transaction(self, tx_hash: str) -> Optional[TxData]:
        """Get transaction by hash.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Transaction data or None if not found
        """
        try:
            return await self.async_web3.eth.get_transaction(tx_hash)
        except TransactionNotFound:
            return None
    
    async def get_transaction_receipt(self, tx_hash: str) -> Optional[TxReceipt]:
        """Get transaction receipt.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Transaction receipt or None if not found
        """
        try:
            return await self.async_web3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            return None
    
    async def wait_for_transaction_receipt(
        self, 
        tx_hash: str, 
        timeout: float = 120.0,
        poll_latency: float = 0.1
    ) -> Optional[TxReceipt]:
        """Wait for transaction receipt with timeout.
        
        Args:
            tx_hash: Transaction hash
            timeout: Timeout in seconds
            poll_latency: Polling interval in seconds
            
        Returns:
            Transaction receipt or None if timeout
        """
        try:
            return await asyncio.wait_for(
                self.async_web3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=timeout, poll_latency=poll_latency
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout waiting for transaction receipt: {tx_hash}")
            return None
    
    async def get_transaction_status(
        self, 
        tx_hash: str, 
        required_confirmations: int = 1
    ) -> TransactionStatus:
        """Get comprehensive transaction status.
        
        Args:
            tx_hash: Transaction hash
            required_confirmations: Required confirmations
            
        Returns:
            TransactionStatus object
        """
        tx_hash_bytes = HexBytes(tx_hash)
        
        # Try to get transaction receipt
        receipt = await self.get_transaction_receipt(tx_hash)
        
        if not receipt:
            # Check if transaction exists in mempool
            tx = await self.get_transaction(tx_hash)
            if tx:
                return TransactionStatus(
                    hash=tx_hash_bytes,
                    status="pending"
                )
            else:
                return TransactionStatus(
                    hash=tx_hash_bytes,
                    status="not_found"
                )
        
        # Transaction is mined
        latest_block = await self.async_web3.eth.block_number
        confirmations = latest_block - receipt["blockNumber"] + 1
        
        # Check if transaction succeeded
        if receipt["status"] == 0:
            status = "failed"
        elif confirmations >= required_confirmations:
            status = "confirmed"
        else:
            status = "pending"
        
        return TransactionStatus(
            hash=tx_hash_bytes,
            status=status,
            block_number=receipt["blockNumber"],
            confirmations=confirmations,
            gas_used=receipt["gasUsed"],
            effective_gas_price=receipt.get("effectiveGasPrice"),
            receipt=receipt
        )
    
    # Gas Estimation Utilities
    
    async def estimate_gas_with_buffer(
        self, 
        transaction: Dict[str, Any], 
        buffer_percent: float = 20.0
    ) -> GasEstimate:
        """Estimate gas with buffer.
        
        Args:
            transaction: Transaction dict
            buffer_percent: Buffer percentage to add
            
        Returns:
            GasEstimate object
        """
        # Get gas estimate
        gas_limit = await self.async_web3.eth.estimate_gas(transaction)
        
        # Add buffer
        buffered_gas_limit = int(gas_limit * (1 + buffer_percent / 100))
        
        # Get gas price information
        gas_price_info = await self._get_gas_price_info()
        
        return GasEstimate(
            gas_limit=buffered_gas_limit,
            gas_price=gas_price_info.gas_price,
            max_fee_per_gas=gas_price_info.max_fee_per_gas,
            max_priority_fee_per_gas=gas_price_info.max_priority_fee_per_gas,
            is_eip1559=gas_price_info.is_eip1559
        )
    
    async def _get_gas_price_info(self) -> GasEstimate:
        """Get current gas price information with caching."""
        current_time = time.time()
        
        # Check cache
        if (self._gas_price_cache and 
            current_time - self._gas_price_cache[0] < self._gas_price_cache_ttl):
            return self._gas_price_cache[1]
        
        try:
            # Try EIP-1559 gas estimation first
            latest_block = await self.get_latest_block()
            
            if latest_block.get("baseFeePerGas"):
                # EIP-1559 supported
                base_fee = latest_block["baseFeePerGas"]
                
                # Get suggested priority fee (fallback to 1.5 gwei)
                try:
                    max_priority_fee = await self.async_web3.eth.max_priority_fee
                except:
                    max_priority_fee = Wei(1_500_000_000)  # 1.5 gwei
                
                # Calculate max fee (base fee + priority fee + buffer)
                max_fee_per_gas = Wei(base_fee * 2 + max_priority_fee)  # 100% buffer on base fee
                
                gas_estimate = GasEstimate(
                    gas_limit=0,  # Will be set by caller
                    gas_price=Wei(base_fee + max_priority_fee),
                    max_fee_per_gas=max_fee_per_gas,
                    max_priority_fee_per_gas=max_priority_fee,
                    is_eip1559=True
                )
            else:
                # Legacy gas pricing
                gas_price = await self.async_web3.eth.gas_price
                gas_estimate = GasEstimate(
                    gas_limit=0,  # Will be set by caller
                    gas_price=gas_price,
                    is_eip1559=False
                )
            
            # Cache result
            self._gas_price_cache = (current_time, gas_estimate)
            return gas_estimate
            
        except Exception as e:
            self.logger.error(f"Error getting gas price info: {e}")
            # Fallback to basic gas price
            gas_price = await self.async_web3.eth.gas_price
            return GasEstimate(
                gas_limit=0,
                gas_price=gas_price,
                is_eip1559=False
            )
    
    # Event and Log Utilities
    
    async def get_logs(
        self, 
        filter_params: FilterParams,
        batch_size: int = 1000
    ) -> List[LogReceipt]:
        """Get logs with automatic batching for large ranges.
        
        Args:
            filter_params: Filter parameters
            batch_size: Maximum logs per batch
            
        Returns:
            List of log receipts
        """
        all_logs = []
        
        from_block = filter_params.get("fromBlock", "latest")
        to_block = filter_params.get("toBlock", "latest")
        
        # Convert block identifiers to numbers
        if from_block == "latest":
            from_block = await self.async_web3.eth.block_number
        elif isinstance(from_block, str) and from_block.startswith("0x"):
            from_block = int(from_block, 16)
        
        if to_block == "latest":
            to_block = await self.async_web3.eth.block_number
        elif isinstance(to_block, str) and to_block.startswith("0x"):
            to_block = int(to_block, 16)
        
        # Calculate batch ranges
        current_from = from_block
        
        while current_from <= to_block:
            current_to = min(current_from + batch_size - 1, to_block)
            
            batch_filter = dict(filter_params)
            batch_filter["fromBlock"] = current_from
            batch_filter["toBlock"] = current_to
            
            try:
                logs = await self.async_web3.eth.get_logs(batch_filter)
                all_logs.extend(logs)
                
                self.logger.debug(
                    f"Retrieved {len(logs)} logs for blocks {current_from}-{current_to}"
                )
                
            except Exception as e:
                self.logger.error(
                    f"Error getting logs for blocks {current_from}-{current_to}: {e}"
                )
                # Try smaller batch size
                if batch_size > 100:
                    batch_size = batch_size // 2
                    continue
                else:
                    raise
            
            current_from = current_to + 1
        
        return all_logs
    
    # Nonce Management
    
    async def get_transaction_count(
        self, 
        address: str, 
        block: str = "pending"
    ) -> int:
        """Get transaction count (nonce) for address.
        
        Args:
            address: Address to check
            block: Block identifier ("pending", "latest", or block number)
            
        Returns:
            Transaction count
        """
        return await self.async_web3.eth.get_transaction_count(
            Web3.to_checksum_address(address), block
        )
    
    # Chain Utilities
    
    async def get_chain_id(self) -> int:
        """Get chain ID."""
        return await self.async_web3.eth.chain_id
    
    async def is_syncing(self) -> Union[bool, Dict[str, Any]]:
        """Check if node is syncing.
        
        Returns:
            False if not syncing, or dict with sync status
        """
        return await self.async_web3.eth.syncing
    
    # Utility Functions
    
    def to_wei(self, amount: Union[int, float, str, Decimal], unit: str = "ether") -> Wei:
        """Convert amount to Wei.
        
        Args:
            amount: Amount to convert
            unit: Unit name (wei, gwei, ether, etc.)
            
        Returns:
            Amount in Wei
        """
        return Web3.to_wei(amount, unit)
    
    def from_wei(self, amount: Wei, unit: str = "ether") -> Decimal:
        """Convert Wei to other unit.
        
        Args:
            amount: Amount in Wei
            unit: Target unit name
            
        Returns:
            Converted amount as Decimal
        """
        return Web3.from_wei(amount, unit)
    
    def keccak(self, data: Union[str, bytes]) -> HexBytes:
        """Calculate Keccak-256 hash.
        
        Args:
            data: Data to hash
            
        Returns:
            Keccak-256 hash
        """
        if isinstance(data, str):
            return Web3.keccak(text=data)
        else:
            return Web3.keccak(data)
    
    def encode_abi(self, types: List[str], values: List[Any]) -> bytes:
        """Encode data according to ABI types.
        
        Args:
            types: List of ABI types
            values: List of values to encode
            
        Returns:
            Encoded data
        """
        return Web3.codec.encode(types, values)
    
    def decode_abi(self, types: List[str], data: bytes) -> Tuple[Any, ...]:
        """Decode data according to ABI types.
        
        Args:
            types: List of ABI types
            data: Data to decode
            
Returns:
            Decoded values
        """
        return Web3.codec.decode(types, data)
    
    # Contract Utilities
    
    def get_contract(self, address: str, abi: List[Dict[str, Any]]):
        """Get contract instance.
        
        Args:
            address: Contract address
            abi: Contract ABI
            
        Returns:
            Contract instance
        """
        return self.web3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=abi
        )
    
    async def call_contract_function(
        self, 
        contract_address: str,
        function_signature: str,
        args: List[Any] = None,
        block: str = "latest"
    ) -> Any:
        """Call contract function (read-only).
        
        Args:
            contract_address: Contract address
            function_signature: Function signature (e.g., "balanceOf(address)")
            args: Function arguments
            block: Block identifier
            
        Returns:
            Function result
        """
        args = args or []
        
        # Create function selector
        function_selector = Web3.keccak(text=function_signature)[:4]
        
        # For simple cases, we'll just make a direct call
        # In a real implementation, you'd want to properly encode the arguments
        call_data = function_selector
        
        result = await self.async_web3.eth.call({
            "to": Web3.to_checksum_address(contract_address),
            "data": call_data.hex()
        }, block)
        
        return result
    
    # Error Handling Utilities
    
    def parse_revert_reason(self, receipt: TxReceipt) -> Optional[str]:
        """Parse revert reason from transaction receipt.
        
        Args:
            receipt: Transaction receipt
            
        Returns:
            Revert reason string or None
        """
        if receipt["status"] == 1:
            return None  # Transaction succeeded
        
        # Try to get revert reason
        try:
            # This is a simplified version - real implementation would
            # need to decode the revert data properly
            return "Transaction reverted"
        except Exception:
            return "Unknown revert reason"
    
    # Connection Health
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Web3 connection.
        
        Returns:
            Health check results
        """
        start_time = time.time()
        health_data = {
            "healthy": False,
            "response_time": 0.0,
            "chain_id": None,
            "latest_block": None,
            "syncing": None,
            "errors": []
        }
        
        try:
            # Check chain ID
            chain_id = await self.get_chain_id()
            health_data["chain_id"] = chain_id
            
            if chain_id != self.config.chain_id:
                health_data["errors"].append(
                    f"Chain ID mismatch: expected {self.config.chain_id}, got {chain_id}"
                )
            
            # Check latest block
            latest_block = await self.async_web3.eth.block_number
            health_data["latest_block"] = latest_block
            
            # Check sync status
            syncing = await self.is_syncing()
            health_data["syncing"] = syncing
            
            if syncing:
                health_data["errors"].append("Node is syncing")
            
            # Calculate response time
            health_data["response_time"] = time.time() - start_time
            
            # Determine overall health
            health_data["healthy"] = len(health_data["errors"]) == 0
            
        except Exception as e:
            health_data["errors"].append(f"Health check failed: {str(e)}")
            health_data["response_time"] = time.time() - start_time
        
        return health_data