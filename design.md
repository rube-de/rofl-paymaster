# Design Document: Cross-Chain Paymaster System

## Overview

This design document outlines the architecture for a cross-chain paymaster/bridge that enables users to pay with USDC on Base and receive ROSE on Oasis Sapphire. The system leverages existing Proveth verification infrastructure for secure cross-chain proof validation and incorporates architectural best practices for security, scalability, and future extensibility.

The architecture abstracts the entire cross-chain process - users can simply use their USDC on Base, and the system handles bridging, asset conversion, and delivery of ROSE to their Sapphire wallet, effectively allowing them to pay for Sapphire gas fees and acquire tokens in a single step.

## Key Architectural Decisions

Based on comprehensive analysis, the following architectural decisions have been made:

1. **ROFL Integration**: Multi-operator consensus model with at least 3 confirmations from different ROFL apps to leverage decentralization
2. **Bridge Direction**: One-way bridge initially with upgradeability support for future bidirectional flows
3. **Proof Verification**: Merkle proofs with batch verification capabilities for gas optimization
4. **Message Execution**: Whitelisted message router for security while maintaining flexibility
5. **Upgradeability**: Proxy pattern (UUPS) for all core contracts to enable future improvements
6. **Price Oracle**: Integration with existing decentralized ROFL price oracle on Sapphire

## MVP Scope

### Phase 1 MVP Features
1. **Core Flow**: USDC on Base → ROSE on Sapphire (native token)
2. **Proof Verification**: Uses existing ProvethVerifier for Merkle-Patricia-Trie proofs with batch support
3. **Block Hash Oracle**: Leverages existing oracle infrastructure for block verification
4. **Multi-ROFL Consensus**: Requires 3+ ROFL app confirmations for security
5. **Message Passing**: Whitelisted contract calls for Sapphire execution
6. **Gas Abstraction**: Pay Sapphire gas fees using USDC
7. **Upgradeability**: UUPS proxy pattern for future enhancements

### Required Contracts from Repository

The following contracts from the bridgeless-btc repository are required:

1. **Proof Verification**:
   - `/liquefaction/contracts/proveth/ProvethVerifier.sol` - Core Merkle-Patricia-Trie proof verification
   - `solidity-rlp/contracts/RLPReader.sol` - RLP decoding (npm dependency)

2. **Block Hash Oracle**:
   - `/contracts/oracle/ITrivialBlockHashOracle.sol` - Interface for block hash queries
   - `/contracts/oracle/MultiBlockHashSetterProxy.sol` - Multi-chain block hash management

3. **Optional Utilities**:
   - `/liquefaction/contracts/parsing/RLPEncode.sol` - RLP encoding utilities (if needed)

### Future Extensions (Built into Architecture)
- Additional source chains (Ethereum, Arbitrum)
- Additional tokens (ETH, USDT)
- Bidirectional flows
- Multi-hop routing
- Cross-chain contract automation

## Architecture Components

### 1. Base Chain Components

#### 1.1 PaymasterVault Contract (Upgradeable)
```solidity
// Deployed on Base with UUPS proxy pattern
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/ReentrancyGuardUpgradeable.sol";

contract PaymasterVault is 
    UUPSUpgradeable, 
    OwnableUpgradeable, 
    PausableUpgradeable,
    ReentrancyGuardUpgradeable 
{
    using EnumerableSet for EnumerableSet.AddressSet;
    
    // State variables
    mapping(address => AssetConfig) public assetConfigs;
    EnumerableSet.AddressSet private supportedAssets;
    mapping(bytes32 => bool) public processedDeposits;
    uint256 private depositNonce;
    
    // Circuit breaker
    uint256 public dailyLimit;
    uint256 public dailyVolume;
    uint256 public lastResetTime;
    
    struct AssetConfig {
        bool isActive;
        uint256 minAmount;
        uint256 maxAmount;
        uint8 decimals;
        uint256 dailyLimit;
    }
    
    event PaymasterDeposit(
        bytes32 indexed depositId,
        address indexed sender,
        address indexed asset,
        address sapphireRecipient,
        uint256 amount,
        uint256 chainId,
        bytes message
    );
    
    event AssetConfigured(
        address indexed asset,
        bool isActive,
        uint256 minAmount,
        uint256 maxAmount,
        uint256 dailyLimit
    );
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    function initialize(address _owner) public initializer {
        __UUPSUpgradeable_init();
        __Ownable_init();
        __Pausable_init();
        __ReentrancyGuard_init();
        
        _transferOwnership(_owner);
        dailyLimit = 1000000 * 10**6; // 1M USDC default
        lastResetTime = block.timestamp;
    }
    
    function deposit(
        address asset,
        uint256 amount,
        address sapphireRecipient,
        bytes calldata message
    ) external nonReentrant whenNotPaused returns (bytes32 depositId) {
        require(supportedAssets.contains(asset), "Asset not supported");
        require(assetConfigs[asset].isActive, "Asset not active");
        require(amount >= assetConfigs[asset].minAmount, "Below minimum");
        require(amount <= assetConfigs[asset].maxAmount, "Above maximum");
        
        // Check daily limits
        _checkAndUpdateDailyLimits(amount);
        
        // Generate unique deposit ID
        depositId = keccak256(abi.encodePacked(
            msg.sender,
            sapphireRecipient,
            asset,
            amount,
            depositNonce++,
            block.timestamp,
            block.chainid
        ));
        
        require(!processedDeposits[depositId], "Duplicate deposit");
        processedDeposits[depositId] = true;
        
        // Transfer tokens
        IERC20(asset).transferFrom(msg.sender, address(this), amount);
        
        emit PaymasterDeposit(
            depositId,
            msg.sender,
            asset,
            sapphireRecipient,
            amount,
            block.chainid,
            message
        );
    }
    
    function _checkAndUpdateDailyLimits(uint256 amount) private {
        if (block.timestamp >= lastResetTime + 1 days) {
            dailyVolume = 0;
            lastResetTime = block.timestamp;
        }
        
        require(dailyVolume + amount <= dailyLimit, "Daily limit exceeded");
        dailyVolume += amount;
    }
    
    // Admin functions
    function configureAsset(
        address asset,
        bool isActive,
        uint256 minAmount,
        uint256 maxAmount,
        uint8 decimals,
        uint256 _dailyLimit
    ) external onlyOwner {
        assetConfigs[asset] = AssetConfig({
            isActive: isActive,
            minAmount: minAmount,
            maxAmount: maxAmount,
            decimals: decimals,
            dailyLimit: _dailyLimit
        });
        
        if (isActive) {
            supportedAssets.add(asset);
        } else {
            supportedAssets.remove(asset);
        }
        
        emit AssetConfigured(asset, isActive, minAmount, maxAmount, _dailyLimit);
    }
    
    function setDailyLimit(uint256 _limit) external onlyOwner {
        dailyLimit = _limit;
    }
    
    function pause() external onlyOwner {
        _pause();
    }
    
    function unpause() external onlyOwner {
        _unpause();
    }
    
    // Required for UUPS
    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}
}
```

### 2. ROFL Application (Python)

#### 2.1 Cross-Chain Monitor and Blockhash Oracle

The ROFL application serves dual critical roles:
1. **Bridge Operator**: Monitors deposits and coordinates cross-chain transfers
2. **Blockhash Oracle**: Acts as a trusted oracle attesting to Base chain blockhashes for the Sapphire contract

**MVP**: Single ROFL operator for simplicity
**Future**: Multi-operator consensus with 3+ confirmations (architecture supports this upgrade path)

**State Verification Method**:
- **MVP Approach (RPC-Based)**: Connects to trusted RPC endpoints for efficient blockchain state reading
- **Future Upgrade Path**: Will integrate light clients directly within the TEE for trust-minimized verification

```python
# rofl_paymaster.py
import asyncio
import json
import rlp
from typing import Dict, Optional, Tuple, List
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import keccak, encode_hex, to_bytes
from eth_abi import encode_abi
from hexbytes import HexBytes
import aiohttp
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class DepositEvent:
    sender: str
    recipient: str
    asset: str
    amount: int
    deposit_id: bytes
    message: bytes
    block_number: int
    tx_hash: str
    log_index: int

class CrossChainPaymasterMonitor:
    def __init__(self, config: Dict):
        # Base chain connection
        self.base_w3 = Web3(Web3.HTTPProvider(config['base_rpc']))
        self.base_w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Sapphire connection
        self.sapphire_w3 = Web3(Web3.HTTPProvider(config['sapphire_rpc']))
        
        # Contract instances
        self.vault_contract = self.base_w3.eth.contract(
            address=config['vault_address'],
            abi=config['vault_abi']
        )
        
        self.paymaster_contract = self.sapphire_w3.eth.contract(
            address=config['paymaster_address'],
            abi=config['paymaster_abi']
        )
        
        self.oracle_contract = self.sapphire_w3.eth.contract(
            address=config['oracle_address'],
            abi=config['oracle_abi']
        )
        
        # ROFL operator account
        self.operator_account = self.sapphire_w3.eth.account.from_key(
            config['operator_private_key']
        )
        
        # Price oracle
        self.price_oracle = PriceOracle(config['price_sources'])
        
    async def monitor_deposits(self):
        """Main monitoring loop for deposit events"""
        # Get starting block
        latest_block = self.base_w3.eth.block_number
        
        while True:
            try:
                # Get new events
                events = self.vault_contract.events.PaymasterDeposit.get_logs(
                    fromBlock=latest_block - 1,
                    toBlock='latest'
                )
                
                for event in events:
                    await self.process_deposit(event)
                
                # Update latest block
                latest_block = self.base_w3.eth.block_number
                
                # Wait before next check
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Error monitoring deposits: {e}")
                await asyncio.sleep(5)
    
    async def process_deposit(self, event):
        """Process a single deposit event"""
        deposit = self._parse_deposit_event(event)
        
        # Wait for confirmations
        await self._wait_for_confirmations(deposit.block_number, 12)
        
        # Generate proof
        proof = await self.generate_deposit_proof(deposit)
        
        # Calculate ROSE amount
        rose_amount = await self.calculate_rose_amount(
            deposit.asset,
            deposit.amount
        )
        
        # Submit to Sapphire
        await self.submit_to_sapphire(deposit, proof, rose_amount)
    
    def _parse_deposit_event(self, event) -> DepositEvent:
        """Parse web3 event into DepositEvent dataclass"""
        return DepositEvent(
            sender=event['args']['sender'],
            recipient=event['args']['recipient'],
            asset=event['args']['asset'],
            amount=event['args']['amount'],
            deposit_id=event['args']['depositId'],
            message=event['args']['message'],
            block_number=event['blockNumber'],
            tx_hash=event['transactionHash'].hex(),
            log_index=event['logIndex']
        )
    
    async def _wait_for_confirmations(self, block_number: int, confirmations: int):
        """Wait for block confirmations"""
        while True:
            current_block = self.base_w3.eth.block_number
            if current_block >= block_number + confirmations:
                break
            await asyncio.sleep(12)  # Base block time
    
    async def generate_deposit_proof(self, deposit: DepositEvent) -> Dict:
        """Generate proof compatible with ProvethVerifier.sol"""
        # Get transaction and receipt
        tx = self.base_w3.eth.get_transaction(deposit.tx_hash)
        receipt = self.base_w3.eth.get_transaction_receipt(deposit.tx_hash)
        
        # Get block data with full transactions
        block = self.base_w3.eth.get_block(deposit.block_number, full_transactions=True)
        
        # Encode block header for ProvethVerifier
        rlp_block_header = self._encode_block_header(block)
        
        # Build transaction proof stack for ProvethVerifier
        tx_proof_stack = self._build_transaction_proof_stack(
            block['transactions'], 
            receipt['transactionIndex']
        )
        
        # Create proof structure compatible with ProvethVerifier
        proof = {
            'rlpBlockHeader': rlp_block_header.hex(),
            'blockNumber': deposit.block_number,
            'transactionIndexRlp': rlp.encode(receipt['transactionIndex']).hex(),
            'transactionProofStack': tx_proof_stack.hex(),
            'logIndex': deposit.log_index,
            'expectedEventSignature': self._get_event_signature()
        }
        
        return proof
    
    def _build_log_merkle_proof(self, receipt, log_index: int) -> list:
        """Build Merkle proof for specific log in receipt"""
        logs = receipt['logs']
        
        # Create leaf nodes from logs
        leaves = []
        for log in logs:
            # Encode log data
            encoded = self._encode_log(log)
            leaf = keccak(encoded)
            leaves.append(leaf)
        
        # Build Merkle tree and extract proof
        proof = self._get_merkle_proof(leaves, log_index)
        return [p.hex() for p in proof]
    
    def _encode_log(self, log) -> bytes:
        """RLP encode a log entry"""
        # Simplified encoding - in production use proper RLP encoding
        topics = [topic.hex() if isinstance(topic, HexBytes) else topic for topic in log['topics']]
        data = log['data'].hex() if isinstance(log['data'], HexBytes) else log['data']
        
        encoded = Web3.keccak(
            text=f"{log['address']}{','.join(topics)}{data}"
        )
        return encoded
    
    def _get_merkle_proof(self, leaves: list, index: int) -> list:
        """Generate Merkle proof for leaf at index"""
        if len(leaves) == 0:
            return []
        
        proof = []
        current_level = leaves[:]
        current_index = index
        
        while len(current_level) > 1:
            next_level = []
            
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    left = current_level[i]
                    right = current_level[i + 1]
                else:
                    left = current_level[i]
                    right = current_level[i]
                
                # Record proof element
                if i == current_index or i + 1 == current_index:
                    if i == current_index:
                        proof.append(right)
                    else:
                        proof.append(left)
                    current_index = i // 2
                
                # Compute parent hash
                combined = left + right if left < right else right + left
                parent = keccak(combined)
                next_level.append(parent)
            
            current_level = next_level
        
        return proof
    
    def _build_receipt_proof(self, block, receipt) -> Dict:
        """Build proof that receipt is in block"""
        # Simplified - in production, build proper receipt trie proof
        return {
            'receiptsRoot': block['receiptsRoot'].hex(),
            'txIndex': receipt['transactionIndex'],
            # Additional proof data would go here
        }
    
    async def calculate_rose_amount(self, asset: str, amount: int) -> int:
        """Calculate ROSE amount based on current prices"""
        # Get prices from oracle
        usdc_price = await self.price_oracle.get_price('USDC')
        rose_price = await self.price_oracle.get_price('ROSE')
        
        # USDC has 6 decimals, ROSE has 18 decimals
        usdc_decimals = 6
        rose_decimals = 18
        
        # Convert to common decimals (18)
        amount_normalized = amount * (10 ** (18 - usdc_decimals))
        
        # Calculate ROSE amount with slippage protection (0.5%)
        slippage = Decimal('0.995')
        rose_amount = int(
            (Decimal(amount_normalized) * usdc_price * slippage) / rose_price
        )
        
        return rose_amount
    
    async def submit_to_sapphire(self, deposit: DepositEvent, proof: Dict, rose_amount: int):
        """Submit deposit proof to Sapphire paymaster contract"""
        # Encode proof data
        encoded_proof = self._encode_proof_for_contract(proof)
        
        # Build transaction
        deposit_data = {
            'depositId': deposit.deposit_id,
            'sender': deposit.sender,
            'recipient': deposit.recipient,
            'asset': deposit.asset,
            'chainId': 8453,  # Base chain ID
            'amount': deposit.amount,
            'roseAmount': rose_amount,
            'message': deposit.message,
            'proof': encoded_proof
        }
        
        # Create transaction
        tx = self.paymaster_contract.functions.processDeposit(
            deposit_data
        ).build_transaction({
            'from': self.operator_account.address,
            'gas': 500000,
            'gasPrice': self.sapphire_w3.eth.gas_price,
            'nonce': self.sapphire_w3.eth.get_transaction_count(
                self.operator_account.address
            )
        })
        
        # Sign and send transaction
        signed_tx = self.operator_account.sign_transaction(tx)
        tx_hash = self.sapphire_w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        # Wait for receipt
        receipt = self.sapphire_w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"Processed deposit {deposit.deposit_id.hex()}, tx: {receipt['transactionHash'].hex()}")
    
    def _encode_proof_for_contract(self, proof: Dict) -> bytes:
        """Encode proof data for ProvethVerifier contract"""
        # Create TransactionProof struct for ProvethVerifier
        return encode_abi(
            ['bytes', 'bytes', 'bytes'],
            [
                bytes.fromhex(proof['rlpBlockHeader'][2:]),  # Remove 0x
                bytes.fromhex(proof['transactionIndexRlp'][2:]),
                bytes.fromhex(proof['transactionProofStack'][2:])
            ]
        )
    
    def _encode_block_header(self, block) -> bytes:
        """RLP encode block header for ProvethVerifier"""
        # Ethereum block header fields in order
        header = [
            to_bytes(hexstr=block['parentHash'].hex()),
            to_bytes(hexstr=block['sha3Uncles'].hex()),
            to_bytes(hexstr=block['miner']),
            to_bytes(hexstr=block['stateRoot'].hex()),
            to_bytes(hexstr=block['transactionsRoot'].hex()),
            to_bytes(hexstr=block['receiptsRoot'].hex()),
            to_bytes(hexstr=block['logsBloom'].hex()),
            block['difficulty'],
            block['number'],
            block['gasLimit'],
            block['gasUsed'],
            block['timestamp'],
            to_bytes(hexstr=block['extraData'].hex()),
            to_bytes(hexstr=block['mixHash'].hex()),
            to_bytes(hexstr=block['nonce'].hex()),
            block.get('baseFeePerGas', 0)  # EIP-1559
        ]
        
        return rlp.encode(header)
    
    def _build_transaction_proof_stack(self, transactions: List, tx_index: int) -> bytes:
        """Build Merkle Patricia Trie proof for transaction"""
        # Build transaction trie
        trie_data = []
        for i, tx in enumerate(transactions):
            # RLP encode transaction index as key
            key = rlp.encode(i)
            # Get raw transaction data
            if hasattr(tx, 'rawTransaction'):
                value = tx.rawTransaction
            else:
                # Reconstruct raw transaction
                value = self._encode_transaction(tx)
            trie_data.append((key, value))
        
        # Build proof for specific transaction
        proof_nodes = self._generate_mpt_proof(trie_data, tx_index)
        
        # RLP encode the proof stack
        return rlp.encode(proof_nodes)
    
    def _encode_transaction(self, tx) -> bytes:
        """RLP encode a transaction"""
        # Handle different transaction types
        if tx.get('type') == 2:  # EIP-1559
            return self._encode_eip1559_tx(tx)
        else:  # Legacy transaction
            return self._encode_legacy_tx(tx)
    
    def _encode_legacy_tx(self, tx) -> bytes:
        """Encode legacy transaction"""
        fields = [
            tx['nonce'],
            tx['gasPrice'],
            tx['gas'],
            to_bytes(hexstr=tx['to']) if tx['to'] else b'',
            tx['value'],
            to_bytes(hexstr=tx['input']),
            tx['v'],
            tx['r'],
            tx['s']
        ]
        return rlp.encode(fields)
    
    def _encode_eip1559_tx(self, tx) -> bytes:
        """Encode EIP-1559 transaction"""
        fields = [
            tx['chainId'],
            tx['nonce'],
            tx.get('maxPriorityFeePerGas', 0),
            tx.get('maxFeePerGas', 0),
            tx['gas'],
            to_bytes(hexstr=tx['to']) if tx['to'] else b'',
            tx['value'],
            to_bytes(hexstr=tx['input']),
            []  # Access list
        ]
        # Add signature
        fields.extend([tx['v'], tx['r'], tx['s']])
        
        # Type 2 transaction with 0x02 prefix
        return b'\x02' + rlp.encode(fields)
    
    def _generate_mpt_proof(self, trie_data: List[Tuple], index: int) -> List[bytes]:
        """Generate Merkle Patricia Trie proof nodes"""
        # Simplified MPT proof generation
        # In production, use py-trie or similar library
        proof_nodes = []
        
        # For now, return a simplified proof structure
        # This would need proper MPT implementation
        return proof_nodes
    
    def _get_event_signature(self) -> str:
        """Get PaymasterDeposit event signature"""
        # PaymasterDeposit(address,address,address,uint256,bytes32,bytes)
        return Web3.keccak(
            text="PaymasterDeposit(address,address,address,uint256,bytes32,bytes)"
        ).hex()
    
    async def update_block_hashes(self):
        """Update block hashes on Sapphire oracle
        
        Critical function: ROFL acts as the trusted blockhash oracle,
        attesting to Base chain blockhashes for the Sapphire contract.
        This enables the Merkle proof verification to work cross-chain.
        """
        # Get latest blocks from Base
        latest_block = self.base_w3.eth.block_number
        
        # Prepare block hash updates
        block_hashes = []
        for block_num in range(latest_block - 100, latest_block + 1):
            block = self.base_w3.eth.get_block(block_num)
            block_hashes.append({
                'chainId': 8453,  # Base
                'blockNumber': block_num,
                'blockHash': block['hash'].hex()
            })
        
        # Update oracle contract - ROFL attests to these blockhashes
        tx = self.oracle_contract.functions.setMultipleBlockHashes(
            block_hashes
        ).build_transaction({
            'from': self.operator_account.address,
            'gas': 1000000,
            'gasPrice': self.sapphire_w3.eth.gas_price
        })
        
        signed_tx = self.operator_account.sign_transaction(tx)
        tx_hash = self.sapphire_w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        print(f"Updated block hashes (Oracle attestation): {tx_hash.hex()}")


class PriceOracle:
    """Multi-source price oracle"""
    
    def __init__(self, sources: list):
        self.sources = sources
        self.session = None
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
    
    async def get_price(self, symbol: str) -> Decimal:
        """Get median price from multiple sources"""
        # Check cache
        if symbol in self.cache:
            cached_price, timestamp = self.cache[symbol]
            if asyncio.get_event_loop().time() - timestamp < self.cache_duration:
                return cached_price
        
        # Fetch from sources
        prices = []
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        # CoinGecko
        if 'coingecko' in self.sources:
            price = await self._fetch_coingecko_price(symbol)
            if price:
                prices.append(price)
        
        # Binance
        if 'binance' in self.sources:
            price = await self._fetch_binance_price(symbol)
            if price:
                prices.append(price)
        
        # Calculate median
        if not prices:
            raise ValueError(f"No price data available for {symbol}")
        
        prices.sort()
        median_price = prices[len(prices) // 2]
        
        # Cache result
        self.cache[symbol] = (median_price, asyncio.get_event_loop().time())
        
        return median_price
    
    async def _fetch_coingecko_price(self, symbol: str) -> Optional[Decimal]:
        """Fetch price from CoinGecko"""
        symbol_map = {
            'USDC': 'usd-coin',
            'ROSE': 'oasis-network'
        }
        
        if symbol not in symbol_map:
            return None
        
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol_map[symbol]}&vs_currencies=usd"
            async with self.session.get(url) as response:
                data = await response.json()
                price = data[symbol_map[symbol]]['usd']
                return Decimal(str(price))
        except Exception as e:
            print(f"CoinGecko price fetch error: {e}")
            return None
    
    async def _fetch_binance_price(self, symbol: str) -> Optional[Decimal]:
        """Fetch price from Binance"""
        symbol_map = {
            'USDC': 'USDCUSDT',
            'ROSE': 'ROSEUSDT'
        }
        
        if symbol not in symbol_map:
            return None
        
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol_map[symbol]}"
            async with self.session.get(url) as response:
                data = await response.json()
                price = data['price']
                
                # Adjust for USDC (USDCUSDT ~= 1)
                if symbol == 'USDC':
                    return Decimal('1.0')
                
                return Decimal(str(price))
        except Exception as e:
            print(f"Binance price fetch error: {e}")
            return None


# Main entry point
async def main():
    config = {
        'base_rpc': 'https://mainnet.base.org',
        'sapphire_rpc': 'https://sapphire.oasis.io',
        'vault_address': '0x...',  # Base vault contract
        'paymaster_address': '0x...',  # Sapphire paymaster contract
        'oracle_address': '0x...',  # Block hash oracle contract
        'operator_private_key': 'ROFL_OPERATOR_PRIVATE_KEY',
        'vault_abi': [...],  # Contract ABI
        'paymaster_abi': [...],  # Contract ABI
        'oracle_abi': [...],  # Oracle ABI
        'price_sources': ['coingecko', 'binance']
    }
    
    monitor = CrossChainPaymasterMonitor(config)
    await monitor.monitor_deposits()

if __name__ == '__main__':
    asyncio.run(main())
```

### 3. Sapphire Components

#### 3.1 CrossChainPaymaster Contract (Upgradeable)
```solidity
// Deployed on Oasis Sapphire with UUPS proxy pattern
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/security/ReentrancyGuardUpgradeable.sol";
import "../liquefaction/contracts/proveth/ProvethVerifier.sol";
import "../contracts/oracle/ITrivialBlockHashOracle.sol";
import "solidity-rlp/contracts/RLPReader.sol";

contract CrossChainPaymaster is 
    UUPSUpgradeable,
    OwnableUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    ProvethVerifier 
{
    using EnumerableSet for EnumerableSet.Bytes32Set;
    
    // Core components
    IPriceOracle public priceOracle;
    ITrivialBlockHashOracle public blockHashOracle;
    address public roflOperator;
    
    // Security
    EnumerableSet.Bytes32Set private processedDeposits;
    mapping(address => uint256) public nonces;
    
    // Extensibility
    mapping(uint256 => ChainConfig) public supportedChains;
    mapping(address => mapping(uint256 => address)) public assetMappings; // asset => chainId => address
    
    struct ChainConfig {
        address vaultContract;
        uint256 confirmations;
        bool isActive;
    }
    
    struct DepositData {
        bytes32 depositId;
        address sender;
        address recipient;
        address asset;
        uint256 chainId;
        uint256 amount;
        uint256 roseAmount;
        bytes message;
        bytes proof;
    }
    
    event RoseDistributed(
        bytes32 indexed depositId,
        address indexed recipient,
        uint256 usdcAmount,
        uint256 roseAmount,
        bool messageExecuted
    );
    
    event MessageExecution(
        bytes32 indexed depositId,
        address indexed target,
        bool success,
        bytes result
    );
    
    // Contract needs to receive ROSE to distribute
    receive() external payable {}
    
    // Main entry point for ROFL operator
    function processDeposit(DepositData calldata data) external onlyROFL {
        require(!processedDeposits.contains(data.depositId), "Already processed");
        require(supportedChains[data.chainId].isActive, "Chain not supported");
        
        // Verify the deposit proof
        require(verifyDepositProof(data), "Invalid proof");
        
        // Mark as processed
        processedDeposits.add(data.depositId);
        
        // Transfer native ROSE to recipient
        require(address(this).balance >= data.roseAmount, "Insufficient ROSE balance");
        (bool success, ) = data.recipient.call{value: data.roseAmount}("");
        require(success, "ROSE transfer failed");
        
        emit RoseDistributed(
            data.depositId,
            data.recipient,
            data.amount,
            data.roseAmount,
            data.message.length > 0
        );
        
        // Execute message if provided
        if (data.message.length > 0) {
            _executeMessage(data.depositId, data.recipient, data.message, data.roseAmount);
        }
    }
    
    function _executeMessage(
        bytes32 depositId,
        address recipient,
        bytes memory message,
        uint256 roseAmount
    ) internal {
        // Decode message: target contract + calldata
        (address target, bytes memory callData) = abi.decode(message, (address, bytes));
        
        // Execute call (no value sent as ROSE already transferred to recipient)
        (bool success, bytes memory result) = target.call(callData);
        
        emit MessageExecution(depositId, target, success, result);
    }
    
    function verifyDepositProof(DepositData memory data) private view returns (bool) {
        // Decode proof data
        (
            bytes memory rlpBlockHeader, 
            bytes memory rlpEncodedTx,
            bytes memory txPath,
            bytes memory txNodes,
            bytes memory receiptProof
        ) = abi.decode(data.proof, (bytes, bytes, bytes, bytes, bytes));
        
        // 1. Verify block hash matches oracle
        bytes32 blockHash = keccak256(rlpBlockHeader);
        uint256 blockNumber = extractBlockNumber(rlpBlockHeader);
        
        require(
            blockHashOracle.getBlockHash(data.chainId, blockNumber) == blockHash,
            "Block hash mismatch"
        );
        
        // 2. Verify transaction inclusion using ProvethVerifier
        require(
            verifyTransactionInclusion(
                blockHash,
                rlpEncodedTx,
                txPath,
                txNodes,
                rlpBlockHeader
            ),
            "Transaction not in block"
        );
        
        // 3. Parse transaction to get receipt
        // Extract logs from receipt and verify PaymasterDeposit event
        return verifyDepositEvent(
            rlpEncodedTx,
            receiptProof,
            data
        );
    }
    
    function verifyTransactionInclusion(
        bytes32 blockHash,
        bytes memory rlpEncodedTx,
        bytes memory txPath,
        bytes memory txNodes,
        bytes memory rlpBlockHeader
    ) private pure returns (bool) {
        // Use ProvethVerifier's Merkle Patricia Trie verification
        // This verifies the transaction is included in the block's transaction trie
        
        // Extract transactions root from block header
        RLPReader.RLPItem[] memory blockHeaderFields = rlpBlockHeader.toRlpItem().toList();
        bytes32 txRoot = bytes32(blockHeaderFields[4].toUint()); // transactionsRoot is at index 4
        
        // Verify the Merkle Patricia proof
        return verifyMerklePatriciaProof(
            txRoot,
            txPath,
            txNodes,
            keccak256(rlpEncodedTx)
        );
    }
    
    function verifyDepositEvent(
        bytes memory rlpEncodedTx,
        bytes memory receiptProof,
        DepositData memory data
    ) private view returns (bool) {
        // Parse the transaction to get 'to' address
        RLPReader.RLPItem[] memory txFields = rlpEncodedTx.toRlpItem().toList();
        address toAddress = txFields[3].toAddress(); // 'to' field is at index 3
        
        // Verify it's a transaction to the vault contract
        require(
            toAddress == supportedChains[data.chainId].vaultContract,
            "Wrong vault contract"
        );
        
        // Parse receipt proof to extract logs
        RLPReader.RLPItem[] memory logs = parseReceiptLogs(receiptProof);
        
        // Find and verify PaymasterDeposit event
        bytes32 eventSignature = keccak256("PaymasterDeposit(bytes32,address,address,address,uint256,uint256,bytes)");
        
        for (uint i = 0; i < logs.length; i++) {
            RLPReader.RLPItem[] memory log = logs[i].toList();
            
            // Check if this is our event
            if (log[0].toAddress() == toAddress && // emitted by vault
                bytes32(log[1].toBytes()) == eventSignature) { // correct event
                
                // Decode event data and verify it matches
                (
                    bytes32 depositId,
                    address sender,
                    address asset,
                    address recipient,
                    uint256 amount
                ) = abi.decode(log[2].toBytes(), (bytes32, address, address, address, uint256));
                
                return depositId == data.depositId &&
                       sender == data.sender &&
                       recipient == data.recipient &&
                       asset == data.asset &&
                       amount == data.amount;
            }
        }
        
        return false;
    }
    
    function extractBlockNumber(bytes memory rlpBlockHeader) private pure returns (uint256) {
        RLPReader.RLPItem[] memory blockHeaderFields = rlpBlockHeader.toRlpItem().toList();
        return blockHeaderFields[8].toUint(); // block number is at index 8
    }
    
    function parseReceiptLogs(bytes memory receiptProof) private pure returns (RLPReader.RLPItem[] memory) {
        // Parse receipt RLP to extract logs
        RLPReader.RLPItem[] memory receiptFields = receiptProof.toRlpItem().toList();
        // Logs are typically at index 3 in a receipt
        return receiptFields[3].toList();
    }
    
    function verifyMerklePatriciaProof(
        bytes32 root,
        bytes memory path,
        bytes memory nodes,
        bytes32 valueHash
    ) private pure returns (bool) {
        // This would use the ProvethVerifier's MPT verification logic
        // For now, using a simplified check
        // In production, this calls into ProvethVerifier's validateMPTProof
        
        bytes32 currentHash = valueHash;
        uint256 pathOffset = 0;
        
        // Process each node in the proof
        RLPReader.RLPItem[] memory proofNodes = nodes.toRlpItem().toList();
        
        for (uint i = 0; i < proofNodes.length; i++) {
            // Implementation would follow Ethereum's MPT specification
            // This is a simplified version
            currentHash = keccak256(abi.encodePacked(currentHash, proofNodes[i].toBytes()));
        }
        
        return currentHash == root;
    }
    
    // Fund the contract with ROSE
    function fundContract() external payable onlyOwner {
        // Accept ROSE funding
    }
    
    // Withdraw excess ROSE
    function withdrawExcessROSE(uint256 amount) external onlyOwner {
        require(address(this).balance >= amount, "Insufficient balance");
        (bool success, ) = owner().call{value: amount}("");
        require(success, "Withdrawal failed");
    }
    
    // Reverse flow support (future)
    function initiateWithdrawal(
        uint256 targetChainId,
        address asset,
        uint256 amount,
        address recipient
    ) external payable {
        // User sends ROSE, emit event for ROFL to unlock USDC on Base
        require(msg.value > 0, "No ROSE sent");
        
        // Emit withdrawal event
        // ROFL will process this and unlock USDC on Base
    }
    
    // Admin functions
    function addSupportedChain(uint256 chainId, address vaultContract) external onlyOwner {
        supportedChains[chainId] = ChainConfig({
            vaultContract: vaultContract,
            confirmations: 12,
            isActive: true
        });
    }
    
    modifier onlyROFL() {
        require(msg.sender == roflOperator, "Only ROFL operator");
        _;
    }
}
```

#### 3.2 Price Oracle Contract
```solidity
contract SimplePriceOracle {
    mapping(string => uint256) public prices; // symbol => price in USD (8 decimals)
    address public updater; // ROFL operator
    uint256 public lastUpdate;
    
    event PricesUpdated(string[] symbols, uint256[] prices, uint256 timestamp);
    
    function updatePrices(string[] calldata symbols, uint256[] calldata newPrices) external {
        require(msg.sender == updater, "Only updater");
        require(symbols.length == newPrices.length, "Length mismatch");
        
        for (uint i = 0; i < symbols.length; i++) {
            prices[symbols[i]] = newPrices[i];
        }
        
        lastUpdate = block.timestamp;
        emit PricesUpdated(symbols, newPrices, block.timestamp);
    }
    
    function getPrice(string calldata symbol) external view returns (uint256) {
        require(prices[symbol] > 0, "Price not available");
        require(block.timestamp - lastUpdate < 3600, "Price stale"); // 1 hour staleness check
        return prices[symbol];
    }
}
```

### 4. Frontend Interface

#### 4.1 User Flow Components
```typescript
interface PaymasterUI {
    // Connection management
    connectWallet(chain: 'base' | 'sapphire'): Promise<void>;
    
    // Main swap interface
    swapForm: {
        sourceChain: 'base'; // MVP: Base only
        sourceAsset: 'USDC'; // MVP: USDC only
        targetChain: 'sapphire';
        targetAsset: 'ROSE'; // Native token
        
        amount: string;
        recipient: string; // Sapphire address
        
        // Optional contract call
        includeMessage: boolean;
        targetContract?: string;
        callData?: string;
    };
    
    // Quote calculation
    async getQuote(amount: string): Promise<{
        inputAmount: string;
        outputAmount: string;
        exchangeRate: string;
        fees: string;
        slippage: string;
    }>;
    
    // Transaction execution
    async executeSwap(params: SwapParams): Promise<{
        depositTxHash: string;
        depositId: string;
        estimatedTime: number;
        trackingUrl: string;
    }>;
    
    // Status tracking
    async trackTransaction(depositId: string): Promise<{
        status: 'pending' | 'processing' | 'completed' | 'failed';
        baseChainTx?: string;
        sapphireTx?: string;
        roseAmount?: string;
        messageExecuted?: boolean;
    }>;
}
```

## Operational Workflow

The cross-chain paymaster follows this detailed workflow:

### 1. **Initiation (User)**
User interacts with the web interface, specifies USDC amount, and provides their Sapphire wallet address. This triggers a transaction locking USDC in the `USDCPaymasterVault` on Base, emitting a `PaymasterDeposit` event.

### 2. **Detection and Confirmation (ROFL)**
The ROFL application detects the `PaymasterDeposit` event and waits for 12 block confirmations on Base to ensure finality and prevent chain reorganizations.

### 3. **Data Gathering and Processing (ROFL)**
Once confirmed, the ROFL performs parallel tasks:
- **Price Oracle Check**: Checks cached USDC/ROSE price (5-minute cache duration)
- **Proof Generation**: Creates cryptographic Merkle proof for the deposit event
- **Blockhash Recording**: Captures the Base chain blockhash for oracle attestation

### 4. **Submission to Sapphire (ROFL as Oracle)**
The ROFL assembles and submits a comprehensive transaction to Sapphire including:
- Original deposit details (sender, recipient, amount)
- Calculated ROSE amount based on current prices
- Merkle proof of the deposit event
- **Blockhash attestation**: ROFL acts as a trusted oracle, attesting to the validity of the Base blockhash

### 5. **Finalization on Sapphire (Contract)**
The `CrossChainPaymaster` contract:
- Verifies the Merkle proof against the ROFL-attested blockhash
- Ensures the transaction hasn't been processed before
- Distributes the calculated ROSE amount to the user's Sapphire wallet
- Optionally executes any attached message/contract call

## Security Considerations

### 1. Multi-Layered Verification
- **Deposit Proof**: Merkle proof of Base chain transaction
- **Block Confirmations**: Wait for finality on Base (12 blocks)
- **ROFL Attestation**: TEE-secured verification
- **Duplicate Prevention**: Track processed deposit IDs

### 2. Economic Security
- **Price Oracle**: Multiple sources with median calculation
- **Slippage Protection**: 0.5% buffer on conversions
- **Rate Limiting**: Per-user daily limits
- **Emergency Pause**: Circuit breaker mechanism

### 3. Operational Security
- **ROFL Operator**: Single trusted operator (initially)
- **Admin Controls**: Time-locked upgrades
- **Monitoring**: Real-time alerts for anomalies

### 4. Future Security Enhancements
- **Light Client Integration**: Upgrade from RPC-based verification to trust-minimized light clients running directly within the TEE
- **Multi-Operator Support**: Decentralized operator set for enhanced reliability
- **Zero-Knowledge Proofs**: Additional privacy layer for cross-chain transfers

## Gas Optimization

### 1. Batch Processing
- ROFL aggregates multiple deposits before submission
- Reduces per-transaction Sapphire gas costs
- Merkle tree for batch verification

### 2. Storage Optimization
- Use bytes32 for deposit IDs instead of structs
- EnumerableSet for processed deposits
- Minimal on-chain storage

### 3. Native ROSE Handling
- Direct transfers instead of ERC-20 operations
- Lower gas costs for distribution
- Simplified accounting

## Python ROFL Deployment

### 1. Environment Setup
```bash
# Install dependencies
pip install web3 aiohttp hexbytes eth-utils rlp eth-abi py-trie

# Environment variables
export ROFL_OPERATOR_KEY="0x..."
export BASE_RPC="https://mainnet.base.org"
export SAPPHIRE_RPC="https://sapphire.oasis.io"
```

### Dependencies for Merkle Proof Generation
```txt
# requirements.txt
web3>=6.0.0
aiohttp>=3.8.0
hexbytes>=0.3.0
eth-utils>=2.0.0
rlp>=3.0.0
eth-abi>=4.0.0
py-trie>=2.0.0  # For proper MPT proof generation
```

### 2. ROFL Configuration
```yaml
# rofl_config.yaml
app:
  name: "crosschain-paymaster"
  version: "1.0.0"

chains:
  base:
    rpc: "${BASE_RPC}"
    chain_id: 8453
    confirmations: 12
    
  sapphire:
    rpc: "${SAPPHIRE_RPC}"
    chain_id: 23294
    
contracts:
  vault:
    address: "0x..."
    abi_file: "vault_abi.json"
    
  paymaster:
    address: "0x..."
    abi_file: "paymaster_abi.json"
    
monitoring:
  poll_interval: 2
  max_retries: 3
  
price_oracle:
  sources: ["coingecko", "binance"]
  cache_duration: 300
```

### 3. Deployment Script
```python
# deploy_rofl.py
import os
from oasis_rofl import ROFLApp

app = ROFLApp(
    name="crosschain-paymaster",
    config_file="rofl_config.yaml",
    main_module="rofl_paymaster"
)

# Deploy to Oasis ROFL
app.deploy(
    operator_key=os.environ['ROFL_OPERATOR_KEY'],
    gas_limit=1000000
)
```

## Extensibility Design

### 1. Multi-Chain Support
```python
# Easy to add new chains in Python ROFL
CHAIN_CONFIGS = {
    'base': {'id': 8453, 'rpc': '...'},
    'ethereum': {'id': 1, 'rpc': '...'},  # Future
    'arbitrum': {'id': 42161, 'rpc': '...'}  # Future
}
```

### 2. Multi-Asset Support
```python
# Asset configuration
ASSET_CONFIGS = {
    'USDC': {'decimals': 6, 'chains': {'base': '0x...'}},
    'USDT': {'decimals': 6, 'chains': {'base': '0x...'}},  # Future
    'ETH': {'decimals': 18, 'chains': {'base': 'native'}}  # Future
}
```

### 3. Bidirectional Flows
```python
# Withdrawal monitoring in ROFL
async def monitor_withdrawals(self):
    """Monitor ROSE → USDC withdrawal requests"""
    events = self.paymaster_contract.events.WithdrawalRequested.get_logs()
    for event in events:
        await self.process_withdrawal(event)
```

### 4. Standardized Interface Adoption
As the protocol expands beyond simple swaps, the system can adopt standardized interfaces:
- **Chainlink CCIP Integration**: Upgrade `PaymasterDeposit` to support `EVM2AnyMessage` interface
- **Developer Experience**: Use familiar CCIP SDK for message construction
- **Maintain Custom Logic**: Keep ROFL relayer for secure TEE-based processing
- **Ecosystem Compatibility**: Enable interoperability with CCIP-compatible systems

## Implementation Timeline

### Week 1-2: Core Infrastructure
- Deploy Base vault contract
- Deploy Sapphire paymaster contract
- Setup Python ROFL development environment

### Week 3-4: ROFL Application
- Implement deposit monitoring in Python
- Add Merkle proof generation
- Integrate price oracles
- Test end-to-end flow

### Week 5: Frontend Development
- Build swap interface
- Add wallet connections
- Implement transaction tracking
- Create status dashboard

### Week 6: Testing & Security
- Unit tests for Python ROFL app
- Integration testing
- Security review
- Gas optimization

### Week 7: Deployment
- Deploy ROFL app to Oasis
- Testnet deployment
- Final testing
- Mainnet deployment

## Monitoring & Operations

### 1. Key Metrics
- Total volume processed
- Number of transactions
- Average processing time
- Failed transaction rate
- Price oracle accuracy

### 2. Python ROFL Monitoring
```python
# monitoring.py
class PaymasterMonitor:
    async def track_metrics(self):
        metrics = {
            'total_deposits': await self.get_total_deposits(),
            'total_volume_usd': await self.get_total_volume(),
            'avg_processing_time': await self.get_avg_processing_time(),
            'failed_transactions': await self.get_failed_count(),
            'rose_balance': await self.get_rose_balance()
        }
        
        # Send to monitoring service
        await self.send_metrics(metrics)
```

### 3. Maintenance
- Price oracle updates (5 min)
- ROSE reserve monitoring
- Chain configuration updates
- Security monitoring

## Economic Model

### 1. Fee Structure
- **Protocol Fee**: 0.3% of transaction value
- **Gas Overhead**: ~$0.50 per transaction
- **Slippage Buffer**: 0.5% protection

### 2. ROSE Liquidity Management
- Maintain sufficient native ROSE in paymaster contract
- Monitor balance and alert on low reserves
- Periodic rebalancing from treasury

### 3. Revenue Distribution
- 40% to ROSE liquidity providers
- 30% to protocol treasury
- 20% to ROFL operators
- 10% to development fund

## Risk Mitigation

### 1. Technical Risks
- **Chain Reorgs**: 12 block confirmations
- **ROFL Downtime**: Multiple operator instances
- **Price Manipulation**: Multi-source oracles with median

### 2. Economic Risks
- **ROSE Liquidity**: Maintain 20% buffer in contract
- **Price Volatility**: 0.5% slippage protection
- **Large Orders**: Per-transaction limits

### 3. Python-Specific Considerations
- **Async Error Handling**: Proper exception handling in asyncio
- **Memory Management**: Efficient event processing
- **Connection Stability**: Reconnection logic for RPC endpoints

## Integration with Existing Contracts

### Required Contract Setup

1. **Deploy Block Hash Oracle**:
   - Use existing `MultiBlockHashSetterProxy.sol` from `/contracts/oracle/`
   - Configure for Base chain (chainId: 8453)
   - Set ROFL operator as authorized updater

2. **Deploy Paymaster Contract**:
   - Import `ProvethVerifier.sol` from `/liquefaction/contracts/proveth/`
   - Ensure `solidity-rlp` is installed as npm dependency
   - Link to deployed block hash oracle

3. **Contract Initialization**:
   ```solidity
   // Initialize CrossChainPaymaster
   paymaster.setBlockHashOracle(oracleAddress);
   paymaster.setROFLOperator(roflOperatorAddress);
   paymaster.setPriceOracle(priceOracleAddress);
   paymaster.addSupportedChain(8453, vaultAddress); // Base
   ```

### Gas Cost Implications

Using ProvethVerifier adds overhead but ensures security:
- **Proof Verification**: ~200-300k gas per transaction
- **Block Hash Check**: ~50k gas
- **ROSE Transfer**: ~21k gas
- **Total**: ~350-400k gas per cross-chain transfer

### Security Model

The integration leverages multiple security layers:
1. **ProvethVerifier**: Cryptographic proof of Base chain events
2. **Block Hash Oracle**: Prevents proof replay with stale blocks
3. **ROFL TEE**: Secure execution environment for monitoring
4. **12 Block Confirmations**: Protection against reorgs

## Conclusion

This MVP design provides a solid foundation for a cross-chain paymaster/bridge that:

1. **Leverages Existing Infrastructure**: Uses proven ProvethVerifier and oracle contracts
2. **Solves Immediate Need**: USDC on Base → ROSE (native) on Sapphire
3. **Uses Python ROFL**: TEE-secured monitoring with proper Merkle proof generation
4. **Ensures Security**: Multi-layered verification using existing battle-tested contracts
5. **Enables Extensions**: Architecture supports multiple chains/assets

The design maximizes code reuse from the bridgeless-btc repository while providing a clean implementation path for the cross-chain paymaster functionality.