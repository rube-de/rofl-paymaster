# Design Document: ROFL Cross-Chain Paymaster

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│   Base Chain        │         │  Oasis Sapphire     │
│                     │         │                     │
│  ┌──────────────┐   │         │  ┌──────────────┐  │
│  │ Vault        │   │         │  │  Paymaster   │  │
│  │ Contract     │   │         │  │  Contract    │  │
│  └──────┬───────┘   │         │  └──────▲───────┘  │
│         │           │         │         │           │
│         │           │         │  ┌──────┴───────┐  │
│         │           │         │  │  Blockhash   │  │
│         │           │         │  │  Oracle      │  │
│         │           │         │  └──────▲───────┘  │
│         │           │         │         │           │
│         │           │         │  ┌──────┴───────┐  │
│         │           │         │  │  Price       │  │
│         │           │         │  │  Oracle      │  │
│         │           │         │  └──────▲───────┘  │
└─────────┼───────────┘         └─────────┼───────────┘
          │                               │
          │ Events                        │ Transactions & Reads
          │                               │
          ▼                               │
    ┌─────────────────────────────────────┴──────────┐
    │              ROFL Paymaster (Python)           │
    │                                                │
    │  ┌─────────────┐  ┌──────────────┐  ┌───────┐ │
    │  │  Monitor    │  │ Proof        │  │Oracle │ │
    │  │  Service    │──│ Generator    │  │Service│ │
    │  └─────────────┘  └──────────────┘  └───────┘ │
    │                                                │
    │  ┌─────────────┐  ┌──────────────┐           │
    │  │  Price      │  │ Transaction  │           │
    │  │  Reader     │  │ Manager      │           │
    │  └─────────────┘  └──────────────┘           │
    └────────────────────────────────────────────────┘
```

### 1.2 Component Architecture

```
src/rofl_paymaster/
├── __init__.py
├── __main__.py              # Entry point
├── config.py                # Configuration management
├── monitor/
│   ├── __init__.py
│   ├── deposit_monitor.py   # Base chain event monitoring
│   └── event_processor.py   # Event handling logic
├── proof/
│   ├── __init__.py
│   ├── merkle_proof.py      # Proof generation
│   └── rlp_encoder.py       # RLP encoding utilities
├── oracle/
│   ├── __init__.py
│   ├── price_reader.py      # Read prices from smart contract
│   └── blockhash_oracle.py  # Blockhash attestation
├── transaction/
│   ├── __init__.py
│   ├── builder.py           # Transaction construction
│   └── submitter.py         # Transaction submission
├── models/
│   ├── __init__.py
│   ├── deposit.py           # Deposit data models
│   └── proof.py             # Proof data models
└── utils/
    ├── __init__.py
    ├── web3_helper.py       # Web3 utilities
    └── retry.py             # Retry logic
```

## 2. Core Components Design

### 2.1 Deposit Monitor Service

**Purpose**: Monitor and process deposit events from Base chain vault contract.

```python
class DepositMonitor:
    """
    Monitors PaymasterDeposit events from Base vault contract.
    Handles event detection, confirmation waiting, and processing coordination.
    """
    
    def __init__(self, config: Config):
        self.base_w3 = Web3Helper.create_connection(config.base_rpc)
        self.vault_contract = self.base_w3.eth.contract(
            address=config.vault_address,
            abi=config.vault_abi
        )
        self.confirmations_required = config.confirmations
        self.event_processor = EventProcessor(config)
        self.processed_deposits = set()  # Duplicate prevention
        
    async def start(self):
        """Main monitoring loop with reconnection logic"""
        while True:
            try:
                await self._subscribe_to_events()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(30)
                await self._reconnect()
        
    async def _subscribe_to_events(self):
        """Subscribe to PaymasterDeposit events with WebSocket"""
        # Use WebSocket for real-time events
        event_filter = self.vault_contract.events.PaymasterDeposit.create_filter(
            fromBlock='latest'
        )
        
        while True:
            for event in event_filter.get_new_entries():
                if await self._is_valid_event(event):
                    await asyncio.create_task(self._handle_deposit(event))
            await asyncio.sleep(12)  # Base block time
    
    async def _handle_deposit(self, event: dict):
        """Process a deposit event with confirmation waiting"""
        deposit = DepositEvent.from_event(event)
        
        # Prevent duplicate processing
        if deposit.deposit_id in self.processed_deposits:
            return
        
        logger.info(f"New deposit detected: {deposit.deposit_id.hex()}")
        
        # Wait for confirmations
        await self._wait_for_confirmations(deposit)
        
        # Mark as processed
        self.processed_deposits.add(deposit.deposit_id)
        
        # Process the deposit
        await self.event_processor.process_deposit(deposit)
    
    async def _wait_for_confirmations(self, deposit: DepositEvent):
        """Wait for required block confirmations"""
        while True:
            current_block = self.base_w3.eth.block_number
            confirmations = current_block - deposit.block_number
            
            if confirmations >= self.confirmations_required:
                logger.info(f"Deposit confirmed: {deposit.deposit_id.hex()}")
                break
                
            await asyncio.sleep(12)  # Base block time
```

### 2.2 Proof Generator

**Purpose**: Generate Merkle proofs compatible with ProvethVerifier.sol for deposit verification.

```python
class ProofGenerator:
    """
    Generates cryptographic proofs for deposit events.
    Creates RLP-encoded block headers and Merkle Patricia Trie proofs.
    """
    
    def __init__(self, base_w3: Web3):
        self.w3 = base_w3
        self.block_cache = TTLCache(maxsize=1000, ttl=3600)
        
    async def generate_proof(self, deposit: DepositEvent) -> DepositProof:
        """Generate Merkle proof for deposit verification"""
        start_time = time.time()
        
        try:
            # Get block and transaction data
            block = await self._get_block(deposit.block_number)
            tx = await self._get_transaction(deposit.tx_hash)
            receipt = await self._get_receipt(deposit.tx_hash)
            
            # Validate data integrity
            self._validate_proof_data(deposit, tx, receipt)
            
            # Build proof components
            rlp_block_header = self._encode_block_header(block)
            tx_index_rlp = rlp.encode(tx['transactionIndex'])
            tx_proof_stack = await self._build_transaction_proof(block, tx)
            
            proof = DepositProof(
                rlp_block_header=rlp_block_header.hex(),
                block_number=deposit.block_number,
                transaction_index_rlp=tx_index_rlp.hex(),
                transaction_proof_stack=tx_proof_stack,
                log_index=deposit.log_index,
                expected_event_signature=PAYMASTER_DEPOSIT_SIGNATURE
            )
            
            # Log performance metrics
            duration = time.time() - start_time
            logger.info(f"Proof generated in {duration:.2f}s for {deposit.deposit_id.hex()}")
            
            return proof
            
        except Exception as e:
            logger.error(f"Proof generation failed: {e}")
            raise ProofGenerationError(f"Failed to generate proof: {e}")
    
    def _encode_block_header(self, block: dict) -> bytes:
        """Encode block header in RLP format for EIP-1559 compatibility"""
        header = [
            block['parentHash'],
            block['sha3Uncles'],
            block['miner'],
            block['stateRoot'],
            block['transactionsRoot'],
            block['receiptsRoot'],
            block['logsBloom'],
            block['difficulty'],
            block['number'],
            block['gasLimit'],
            block['gasUsed'],
            block['timestamp'],
            block['extraData'],
            block['mixHash'],
            block['nonce']
        ]
        
        # Add baseFeePerGas for EIP-1559 blocks
        if 'baseFeePerGas' in block and block['baseFeePerGas'] is not None:
            header.append(block['baseFeePerGas'])
        
        return rlp.encode(header)
    
    async def _build_transaction_proof(self, block: dict, tx: dict) -> str:
        """Build Merkle Patricia Trie proof for transaction inclusion"""
        # Get all transactions in block
        all_txs = []
        for tx_hash in block['transactions']:
            tx_data = await self._get_transaction(tx_hash)
            all_txs.append(tx_data)
        
        # Build Merkle Patricia Trie
        trie = MerklePatriciaTrie()
        for i, tx_data in enumerate(all_txs):
            key = rlp.encode(i)
            value = self._encode_transaction(tx_data)
            trie.set(key, value)
        
        # Generate proof for target transaction
        tx_index = tx['transactionIndex']
        proof_path = rlp.encode(tx_index)
        proof_stack = trie.get_proof(proof_path)
        
        return proof_stack.hex()
    
    def _validate_proof_data(self, deposit: DepositEvent, tx: dict, receipt: dict):
        """Validate that proof data matches deposit event exactly"""
        if tx['hash'].hex() != deposit.tx_hash:
            raise ValidationError("Transaction hash mismatch")
        
        if receipt['blockNumber'] != deposit.block_number:
            raise ValidationError("Block number mismatch")
        
        # Find the PaymasterDeposit event in the receipt
        target_log = None
        for log in receipt['logs']:
            if (log['address'].lower() == self.vault_address.lower() and
                log['topics'][0].hex() == PAYMASTER_DEPOSIT_SIGNATURE):
                target_log = log
                break
        
        if not target_log or target_log['logIndex'] != deposit.log_index:
            raise ValidationError("Log index mismatch")
```

### 2.3 Price Reader

**Purpose**: Read USDC/ROSE prices from the deployed price oracle smart contract on Sapphire.

```python
class PriceReader:
    """
    Reads price data from the deployed ROFL price oracle smart contract.
    Provides exchange rates with built-in caching and validation.
    """
    
    def __init__(self, config: Config, sapphire_w3: Web3):
        self.sapphire_w3 = sapphire_w3
        self.price_oracle_contract = sapphire_w3.eth.contract(
            address=config.price_oracle_address,
            abi=config.price_oracle_abi
        )
        self.cache = TTLCache(maxsize=100, ttl=300)  # 5-minute cache
        self.slippage = Decimal(str(config.slippage))
        
    async def get_exchange_rate(self, from_token: str, to_token: str) -> Decimal:
        """Get exchange rate from price oracle contract"""
        cache_key = f"{from_token}_{to_token}"
        
        # Check cache first
        if cache_key in self.cache:
            logger.debug(f"Using cached price for {cache_key}")
            return self.cache[cache_key]
        
        try:
            # Read price from smart contract
            if from_token.upper() == 'USDC' and to_token.upper() == 'ROSE':
                # Call the price oracle contract method
                # Assuming the contract has a method like getPrice(tokenA, tokenB)
                price_data = await self._call_contract_method(
                    'getPrice',
                    [from_token.upper(), to_token.upper()]
                )
                
                # Extract price and validate
                exchange_rate = self._parse_price_data(price_data)
                
                # Validate price is reasonable
                if not self._validate_price(exchange_rate):
                    raise PriceValidationError(f"Invalid price: {exchange_rate}")
                
                # Cache the result
                self.cache[cache_key] = exchange_rate
                
                logger.info(f"Retrieved price from oracle: {cache_key} = {exchange_rate}")
                return exchange_rate
            else:
                raise ValueError(f"Unsupported token pair: {from_token}/{to_token}")
                
        except Exception as e:
            logger.error(f"Failed to read price from oracle: {e}")
            raise PriceOracleError(f"Price oracle read failed: {e}")
    
    async def _call_contract_method(self, method_name: str, params: list):
        """Call price oracle contract method with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                method = getattr(self.price_oracle_contract.functions, method_name)
                result = await method(*params).call()
                return result
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Contract call attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
    
    def _parse_price_data(self, price_data) -> Decimal:
        """Parse price data returned from contract"""
        # Assuming the contract returns a tuple (price, decimals, timestamp)
        # or similar structure
        if isinstance(price_data, (list, tuple)):
            price = price_data[0]  # Price in wei or similar
            decimals = price_data[1] if len(price_data) > 1 else 18
            timestamp = price_data[2] if len(price_data) > 2 else None
            
            # Check if price is stale (older than 1 hour)
            if timestamp and (time.time() - timestamp) > 3600:
                raise PriceValidationError("Price data is stale")
            
            # Convert to decimal with proper scaling
            return Decimal(price) / Decimal(10 ** decimals)
        else:
            # Simple price value
            return Decimal(price_data) / Decimal(10 ** 18)  # Assume 18 decimals
    
    def _validate_price(self, price: Decimal) -> bool:
        """Validate that price is within reasonable bounds"""
        # ROSE price should be between $0.01 and $10 per USDC
        min_price = Decimal('0.01')
        max_price = Decimal('10.0')
        
        return min_price <= price <= max_price
    
    def calculate_output_amount(
        self, 
        input_amount: int, 
        exchange_rate: Decimal
    ) -> int:
        """Calculate ROSE output amount with slippage protection"""
        # Convert USDC (6 decimals) to base units
        usdc_amount = Decimal(input_amount) / Decimal(10**6)
        
        # Calculate ROSE amount using exchange rate
        rose_amount = usdc_amount * exchange_rate
        
        # Apply slippage protection (round down)
        rose_amount_with_slippage = rose_amount * (1 - self.slippage)
        
        # Convert to wei (18 decimals)
        rose_wei = int(rose_amount_with_slippage * Decimal(10**18))
        
        logger.info(f"USDC {usdc_amount} -> ROSE {rose_amount_with_slippage} (rate: {exchange_rate}, slippage: {self.slippage})")
        
        return rose_wei
    
    async def get_oracle_status(self) -> dict:
        """Get price oracle contract status for monitoring"""
        try:
            # Assuming the contract has status methods
            status_data = await self._call_contract_method('getStatus', [])
            
            return {
                'healthy': True,
                'last_update': status_data.get('lastUpdate', 0),
                'price_count': status_data.get('priceCount', 0),
                'oracle_address': self.price_oracle_contract.address
            }
            
        except Exception as e:
            logger.error(f"Failed to get oracle status: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'oracle_address': self.price_oracle_contract.address
            }
```

### 2.4 Blockhash Oracle Service

**Purpose**: Maintain Base chain blockhash attestations on Sapphire oracle contract.

Note: The implementation uses the `ITrivalBlockHashOracle` interface from the liquefaction submodule.

```python
class BlockhashOracle:
    """
    Blockhash attestation service for Base chain.
    Updates Sapphire oracle contract with recent Base blockhashes.
    Implements ITrivalBlockHashOracle interface from liquefaction submodule.
    """
    
    def __init__(self, config: Config, base_w3: Web3, sapphire_w3: Web3):
        self.base_w3 = base_w3
        self.sapphire_w3 = sapphire_w3
        self.oracle_contract = sapphire_w3.eth.contract(
            address=config.blockhash_oracle_address,
            abi=config.blockhash_oracle_abi  # ITrivalBlockHashOracle ABI
        )
        self.update_interval = 50  # blocks
        self.batch_size = 10
        self.max_blocks_stored = 100
        
    async def start(self):
        """Start oracle update loop"""
        logger.info("Starting blockhash oracle service")
        
        while True:
            try:
                await self._update_blockhashes()
                
                # Wait for next update interval
                wait_time = self.update_interval * 12  # Base block time
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Oracle update error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute
    
    async def _update_blockhashes(self):
        """Update blockhashes on Sapphire using ITrivalBlockHashOracle"""
        # Get latest block on Base
        latest_block = self.base_w3.eth.block_number
        
        # Get last updated block from oracle
        try:
            last_updated = await self._get_last_updated_block()
        except Exception as e:
            logger.warning(f"Could not get last updated block: {e}")
            # Start from recent block if oracle is empty
            last_updated = latest_block - 10
        
        # Prepare batch update
        blocks_to_update = []
        block_hashes = []
        
        start_block = max(last_updated + 1, latest_block - self.max_blocks_stored)
        
        for block_num in range(start_block, latest_block + 1):
            if len(blocks_to_update) >= self.batch_size:
                break
                
            try:
                block = self.base_w3.eth.get_block(block_num)
                blocks_to_update.append(block_num)
                block_hashes.append(block['hash'])
            except Exception as e:
                logger.warning(f"Could not fetch block {block_num}: {e}")
                continue
        
        if blocks_to_update:
            await self._submit_batch_update(blocks_to_update, block_hashes)
            logger.info(f"Updated {len(blocks_to_update)} blockhashes")
        else:
            logger.debug("No blockhashes to update")
    
    async def _submit_batch_update(self, block_numbers: list, block_hashes: list):
        """Submit batch blockhash update using ITrivalBlockHashOracle"""
        try:
            # Build transaction using ITrivalBlockHashOracle interface
            tx = self.oracle_contract.functions.setMultipleBlockHashes(
                block_numbers,
                block_hashes
            ).build_transaction({
                'from': self.sapphire_w3.eth.default_account,
                'gas': 500000,  # Generous gas limit for batch update
                'gasPrice': await self._get_gas_price(),
                'nonce': await self._get_nonce()
            })
            
            # Sign with ROFL operator key
            private_key = os.getenv('ROFL_PRIVATE_KEY')
            signed_tx = self.sapphire_w3.eth.account.sign_transaction(tx, private_key)
            
            # Submit transaction
            tx_hash = self.sapphire_w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = await self._wait_for_receipt(tx_hash)
            
            if receipt['status'] != 1:
                raise TransactionFailedError(f"Oracle update failed: {tx_hash.hex()}")
            
            logger.info(f"Blockhash update successful: {tx_hash.hex()}")
            
        except Exception as e:
            logger.error(f"Failed to submit oracle update: {e}")
            raise
    
    async def _get_last_updated_block(self) -> int:
        """Get the last updated block number from oracle contract"""
        try:
            # This assumes the ITrivalBlockHashOracle has a method to get the latest block
            return await self.oracle_contract.functions.getLatestBlockNumber().call()
        except Exception:
            # If method doesn't exist, fallback to checking recent blocks
            current_block = self.base_w3.eth.block_number
            
            # Check the last 100 blocks to find the most recent one in oracle
            for block_num in range(current_block, current_block - 100, -1):
                try:
                    stored_hash = await self.oracle_contract.functions.getBlockHash(block_num).call()
                    if stored_hash != b'\x00' * 32:  # Non-zero hash indicates stored
                        return block_num
                except Exception:
                    continue
            
            # Default to 10 blocks behind if nothing found
            return current_block - 10

    async def _get_gas_price(self) -> int:
        """Get current gas price with some buffer"""
        base_price = self.sapphire_w3.eth.gas_price
        return int(base_price * 1.1)  # 10% buffer
    
    async def _get_nonce(self) -> int:
        """Get transaction nonce for operator account"""
        return self.sapphire_w3.eth.get_transaction_count(
            self.sapphire_w3.eth.default_account,
            'pending'
        )
    
    async def _wait_for_receipt(self, tx_hash: str, timeout: int = 300):
        """Wait for transaction receipt with timeout"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                receipt = self.sapphire_w3.eth.get_transaction_receipt(tx_hash)
                return receipt
            except Exception:
                await asyncio.sleep(5)
        
        raise TimeoutError(f"Transaction {tx_hash.hex()} did not confirm within {timeout}s")
```

### 2.5 Transaction Manager

**Purpose**: Build and submit deposit processing transactions to Sapphire paymaster contract.

```python
class TransactionManager:
    """
    Manages transaction building and submission to Sapphire paymaster contract.
    Handles nonce management, gas estimation, and retry logic.
    """
    
    def __init__(self, config: Config, sapphire_w3: Web3):
        self.sapphire_w3 = sapphire_w3
        self.paymaster_contract = sapphire_w3.eth.contract(
            address=config.paymaster_address,
            abi=config.paymaster_abi
        )
        self.nonce_manager = NonceManager(sapphire_w3)
        self.gas_estimator = GasEstimator(sapphire_w3)
        self.retry_config = RetryConfig(max_attempts=3, backoff_factor=2)
        
    async def process_deposit(
        self,
        deposit: DepositEvent,
        proof: DepositProof,
        rose_amount: int
    ) -> str:
        """Submit deposit processing transaction to Sapphire with retry logic"""
        
        for attempt in range(self.retry_config.max_attempts):
            try:
                tx_hash = await self._submit_deposit_transaction(
                    deposit, proof, rose_amount
                )
                
                # Wait for confirmation
                receipt = await self._wait_for_receipt(tx_hash)
                
                if receipt['status'] == 1:
                    logger.info(f"Deposit processed successfully: {deposit.deposit_id.hex()}")
                    return tx_hash.hex()
                else:
                    raise TransactionFailedError(f"Transaction failed: {tx_hash.hex()}")
                    
            except Exception as e:
                logger.warning(f"Transaction attempt {attempt + 1} failed: {e}")
                
                if attempt == self.retry_config.max_attempts - 1:
                    raise TransactionFailedError(f"All transaction attempts failed: {e}")
                
                # Wait before retry
                await asyncio.sleep(self.retry_config.backoff_factor ** attempt)
    
    async def _submit_deposit_transaction(
        self,
        deposit: DepositEvent,
        proof: DepositProof,
        rose_amount: int
    ) -> str:
        """Build and submit the processDeposit transaction"""
        
        # Prepare deposit data for contract call
        deposit_data = {
            'sender': deposit.sender,
            'recipient': deposit.recipient,
            'asset': deposit.asset,
            'amount': deposit.amount,
            'depositId': deposit.deposit_id,
            'message': deposit.message
        }
        
        # Prepare proof data for contract call
        proof_data = {
            'rlpBlockHeader': proof.rlp_block_header,
            'blockNumber': proof.block_number,
            'transactionIndexRlp': proof.transaction_index_rlp,
            'transactionProofStack': proof.transaction_proof_stack,
            'logIndex': proof.log_index,
            'expectedEventSignature': proof.expected_event_signature
        }
        
        # Build transaction
        tx = self.paymaster_contract.functions.processDeposit(
            deposit_data,
            proof_data,
            rose_amount
        ).build_transaction({
            'from': self.sapphire_w3.eth.default_account,
            'nonce': await self.nonce_manager.get_nonce(),
            'gas': await self._estimate_gas(deposit_data, proof_data, rose_amount),
            'gasPrice': await self._get_gas_price()
        })
        
        # Sign transaction
        private_key = os.getenv('ROFL_PRIVATE_KEY')
        signed_tx = self.sapphire_w3.eth.account.sign_transaction(tx, private_key)
        
        # Submit transaction
        tx_hash = self.sapphire_w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        logger.info(f"Submitted deposit transaction: {tx_hash.hex()}")
        return tx_hash
    
    async def _estimate_gas(self, deposit_data: dict, proof_data: dict, rose_amount: int) -> int:
        """Estimate gas for the processDeposit transaction"""
        try:
            estimated = self.paymaster_contract.functions.processDeposit(
                deposit_data,
                proof_data,
                rose_amount
            ).estimate_gas({
                'from': self.sapphire_w3.eth.default_account
            })
            
            # Add 20% buffer
            return int(estimated * 1.2)
            
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}, using default")
            return 1000000  # Default gas limit
    
    async def _get_gas_price(self) -> int:
        """Get current gas price with buffer"""
        base_price = self.sapphire_w3.eth.gas_price
        return int(base_price * 1.1)  # 10% buffer
    
    async def _wait_for_receipt(self, tx_hash: str, timeout: int = 300):
        """Wait for transaction receipt with timeout"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                receipt = self.sapphire_w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return receipt
            except Exception:
                pass
            
            await asyncio.sleep(5)
        
        raise TimeoutError(f"Transaction {tx_hash.hex()} did not confirm within {timeout}s")

class NonceManager:
    """Manages transaction nonces to prevent conflicts"""
    
    def __init__(self, w3: Web3):
        self.w3 = w3
        self.pending_nonces = {}
        self.lock = asyncio.Lock()
    
    async def get_nonce(self) -> int:
        """Get next available nonce for default account"""
        async with self.lock:
            account = self.w3.eth.default_account
            
            # Get current nonce from network
            network_nonce = self.w3.eth.get_transaction_count(account, 'pending')
            
            # Track pending nonces
            if account not in self.pending_nonces:
                self.pending_nonces[account] = network_nonce
            else:
                self.pending_nonces[account] = max(
                    self.pending_nonces[account] + 1,
                    network_nonce
                )
            
            return self.pending_nonces[account]
```

## 3. Data Flow

### 3.1 Deposit Processing Flow

```
1. User deposits USDC on Base
   └─> Vault Contract emits PaymasterDeposit event
   └─> Event includes: sender, recipient, amount, depositId, message

2. ROFL Monitor detects event via WebSocket
   └─> Parse event data into DepositEvent model
   └─> Wait for 12 block confirmations
   └─> Prevent duplicate processing

3. Event Processor coordinates processing
   └─> Generate Merkle proof
   └─> Read current exchange rate from price oracle contract
   └─> Calculate ROSE output amount
   └─> Submit transaction to Sapphire

4. Proof Generator creates cryptographic proof
   └─> Fetch block header and encode in RLP
   └─> Build Merkle Patricia Trie proof
   └─> Validate proof data integrity

5. Price Reader gets exchange rate from smart contract
   └─> Call price oracle contract on Sapphire
   └─> Validate price data freshness and bounds
   └─> Apply 0.5% slippage protection

6. Transaction Manager submits to Sapphire
   └─> Build processDeposit transaction
   └─> Include proof and calculated ROSE amount
   └─> Handle gas estimation and nonce management
   └─> Submit with retry logic

7. Paymaster Contract on Sapphire verifies and executes
   └─> Verify proof against blockhash oracle
   └─> Transfer ROSE to recipient
   └─> Emit ProcessedDeposit event
```

### 3.2 Price Oracle Integration Flow

```
1. Price Reader queries Sapphire price oracle contract
   └─> Call getPrice(USDC, ROSE) method
   └─> Retrieve price, decimals, and timestamp

2. Price validation and caching
   └─> Validate price is within reasonable bounds ($0.01 - $10)
   └─> Check timestamp is fresh (< 1 hour old)
   └─> Cache result for 5 minutes

3. Exchange rate calculation
   └─> Convert USDC amount to ROSE using oracle price
   └─> Apply slippage protection (default 0.5%)
   └─> Return final ROSE amount in wei
```

### 3.3 Blockhash Oracle Flow

```
1. Oracle Service monitors Base chain continuously
   └─> Track latest block number
   └─> Maintain sliding window of recent blocks

2. Every 50 blocks (or on startup)
   └─> Fetch block hashes from Base RPC
   └─> Prepare batch update (up to 10 blocks)
   └─> Use ITrivalBlockHashOracle interface

3. Submit to Oracle Contract on Sapphire
   └─> Call setMultipleBlockHashes function
   └─> Sign with ROFL operator key
   └─> Handle transaction confirmation

4. Oracle Contract stores hashes
   └─> Available for proof verification
   └─> Maintains recent 100 blocks
   └─> Provides getBlockHash interface
```

## 4. Error Handling Strategy

### 4.1 Connection Management

```python
class ConnectionManager:
    """Manages Web3 connections with failover support"""
    
    def __init__(self, rpc_urls: List[str], chain_name: str):
        self.rpc_urls = rpc_urls
        self.chain_name = chain_name
        self.current_index = 0
        self.connection_pool = {}
        
    async def get_connection(self) -> Web3:
        """Get active connection with automatic failover"""
        for attempt in range(len(self.rpc_urls)):
            url = self.rpc_urls[self.current_index]
            
            try:
                if url not in self.connection_pool:
                    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 30}))
                    self.connection_pool[url] = w3
                
                w3 = self.connection_pool[url]
                
                # Test connection
                await asyncio.wait_for(w3.eth.block_number, timeout=10)
                
                logger.info(f"Connected to {self.chain_name} via {url}")
                return w3
                
            except Exception as e:
                logger.warning(f"{self.chain_name} RPC {url} failed: {e}")
                self.current_index = (self.current_index + 1) % len(self.rpc_urls)
                
                # Remove failed connection from pool
                if url in self.connection_pool:
                    del self.connection_pool[url]
        
        raise ConnectionError(f"All {self.chain_name} RPC endpoints failed")
    
    async def health_check(self) -> bool:
        """Check if current connection is healthy"""
        try:
            w3 = await self.get_connection()
            await asyncio.wait_for(w3.eth.block_number, timeout=5)
            return True
        except Exception:
            return False
```

### 4.2 Price Oracle Error Handling

```python
class PriceOracleErrorHandler:
    """Handle price oracle specific errors"""
    
    def __init__(self, price_reader: PriceReader):
        self.price_reader = price_reader
        self.fallback_cache = {}
        self.error_count = 0
        self.max_errors = 5
        
    async def get_exchange_rate_with_fallback(self, from_token: str, to_token: str) -> Decimal:
        """Get exchange rate with fallback mechanisms"""
        try:
            # Try primary oracle
            rate = await self.price_reader.get_exchange_rate(from_token, to_token)
            
            # Reset error count on success
            self.error_count = 0
            
            # Update fallback cache
            cache_key = f"{from_token}_{to_token}"
            self.fallback_cache[cache_key] = {
                'rate': rate,
                'timestamp': time.time()
            }
            
            return rate
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Price oracle error (count: {self.error_count}): {e}")
            
            # Use fallback cache if available and recent
            cache_key = f"{from_token}_{to_token}"
            if cache_key in self.fallback_cache:
                cached_data = self.fallback_cache[cache_key]
                age = time.time() - cached_data['timestamp']
                
                # Use cached rate if less than 1 hour old
                if age < 3600:
                    logger.warning(f"Using cached rate from {age:.0f}s ago")
                    return cached_data['rate']
            
            # If too many consecutive errors, use emergency rate
            if self.error_count >= self.max_errors:
                logger.critical("Price oracle consistently failing, using emergency rate")
                return self._get_emergency_rate(from_token, to_token)
            
            raise PriceOracleError(f"Price oracle failed: {e}")
    
    def _get_emergency_rate(self, from_token: str, to_token: str) -> Decimal:
        """Get emergency exchange rate when oracle is down"""
        # Conservative emergency rates
        emergency_rates = {
            'USDC_ROSE': Decimal('0.05')  # Conservative 1 USDC = 0.05 ROSE
        }
        
        key = f"{from_token}_{to_token}"
        if key in emergency_rates:
            return emergency_rates[key]
        
        raise PriceOracleError(f"No emergency rate available for {key}")
```

### 4.3 Retry Logic with Circuit Breaker

```python
class RetryWithCircuitBreaker:
    """Retry mechanism with circuit breaker pattern"""
    
    def __init__(self, max_attempts=3, failure_threshold=5, reset_timeout=60):
        self.max_attempts = max_attempts
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    async def execute(self, func, *args, **kwargs):
        """Execute function with retry and circuit breaker"""
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = 'half-open'
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        for attempt in range(self.max_attempts):
            try:
                result = await func(*args, **kwargs)
                
                # Success - reset circuit breaker
                if self.state == 'half-open':
                    self.state = 'closed'
                    self.failure_count = 0
                
                return result
                
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = 'open'
                
                if attempt == self.max_attempts - 1:
                    raise
                
                wait_time = 2 ** attempt  # Exponential backoff
                await asyncio.sleep(wait_time)
        
        raise RetryExhaustedError("All retry attempts failed")
```

## 5. Configuration Management

### 5.1 Configuration Structure

```yaml
# config/config.yaml
rofl:
  environment: "production"  # development, staging, production
  log_level: "INFO"
  private_key_source: "aws_secrets"  # env_var, aws_secrets, azure_keyvault, keyfile
  
  # Rate limiting
  max_deposits_per_hour: 100
  max_deposits_per_minute: 10
  
  # Processing settings
  batch_size: 10
  retry_attempts: 3
  retry_backoff_factor: 2
  slippage: 0.005  # 0.5%

chains:
  base:
    name: "Base Mainnet"
    chain_id: 8453
    rpc_urls:
      - "https://mainnet.base.org"
      - "https://base-mainnet.infura.io/v3/${INFURA_API_KEY}"
      - "https://base-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}"
    websocket_urls:
      - "wss://base-mainnet.infura.io/ws/v3/${INFURA_API_KEY}"
    confirmations: 12
    block_time: 12  # seconds
    
  sapphire:
    name: "Oasis Sapphire Mainnet"
    chain_id: 23294
    rpc_urls:
      - "https://sapphire.oasis.io"
      - "https://1rpc.io/oasis/sapphire"
    confirmations: 6
    block_time: 6  # seconds

contracts:
  vault:
    address: "0x1234567890abcdef1234567890abcdef12345678"
    abi_file: "abis/vault.json"
    deployment_block: 12345678
    
  paymaster:
    address: "0xabcdef1234567890abcdef1234567890abcdef12"
    abi_file: "abis/paymaster.json"
    deployment_block: 1234567
    
  blockhash_oracle:
    address: "0xfedcba0987654321fedcba0987654321fedcba09"
    abi_file: "abis/liquefaction/ITrivalBlockHashOracle.json"  # From liquefaction submodule
    deployment_block: 1234568
    
  price_oracle:
    address: "0x9876543210fedcba9876543210fedcba98765432"
    abi_file: "abis/price_oracle.json"
    deployment_block: 1234569

assets:
  usdc:
    address: "0xA0b86a33E6441Ee78b8b48A3CC7D35D29e38a011"  # Base USDC
    decimals: 6
    min_amount: 1000000      # 1 USDC
    max_amount: 10000000000  # 10,000 USDC
    
  rose:
    decimals: 18
    symbol: "ROSE"

price_oracle:
  cache_ttl: 300  # 5 minutes
  price_validation:
    min_price: 0.01   # $0.01 minimum ROSE price
    max_price: 10.0   # $10.00 maximum ROSE price
    max_age: 3600     # 1 hour max price age
  emergency_rates:
    usdc_rose: 0.05   # Conservative emergency rate

blockhash_oracle:
  update_interval_blocks: 50
  batch_size: 10
  max_blocks_stored: 100
  gas_limit: 500000

monitoring:
  metrics:
    enabled: true
    port: 9090
    path: "/metrics"
    
  logging:
    format: "json"  # json, structured, plain
    level: "INFO"
    max_file_size: "100MB"
    backup_count: 5
    
  health_check:
    enabled: true
    port: 8080
    path: "/health"
    
  alerts:
    webhook_url: "${ALERT_WEBHOOK_URL}"
    alert_on_failure_rate: 0.1  # 10%
    alert_on_processing_delay: 300  # 5 minutes

security:
  address_validation: true
  amount_limits: true
  rate_limiting: true
  suspicious_activity_monitoring: true
  
  # AWS Secrets Manager
  aws:
    region: "us-east-1"
    secret_name: "rofl-paymaster/private-key"
    
  # Azure Key Vault
  azure:
    vault_url: "${AZURE_VAULT_URL}"
    secret_name: "rofl-private-key"
```

## 6. Testing Strategy

### 6.1 Unit Tests

```python
# tests/test_price_reader.py
import pytest
from unittest.mock import Mock, AsyncMock
from decimal import Decimal
from rofl_paymaster.oracle.price_reader import PriceReader

@pytest.fixture
def mock_sapphire_w3():
    """Mock Sapphire Web3 instance"""
    w3 = Mock()
    contract = Mock()
    
    # Mock successful price call
    contract.functions.getPrice.return_value.call = AsyncMock(
        return_value=[500000000000000000, 18, int(time.time())]  # 0.5 ROSE per USDC
    )
    
    w3.eth.contract.return_value = contract
    return w3

@pytest.fixture
def price_reader(mock_sapphire_w3):
    """Price reader instance for testing"""
    config = Mock()
    config.price_oracle_address = '0x1234567890abcdef1234567890abcdef12345678'
    config.price_oracle_abi = []
    config.slippage = 0.005
    
    return PriceReader(config, mock_sapphire_w3)

@pytest.mark.asyncio
async def test_get_exchange_rate_success(price_reader):
    """Test successful exchange rate retrieval"""
    rate = await price_reader.get_exchange_rate('USDC', 'ROSE')
    
    assert rate == Decimal('0.5')

@pytest.mark.asyncio
async def test_get_exchange_rate_caching(price_reader):
    """Test price caching functionality"""
    # First call
    rate1 = await price_reader.get_exchange_rate('USDC', 'ROSE')
    
    # Second call should use cache
    rate2 = await price_reader.get_exchange_rate('USDC', 'ROSE')
    
    assert rate1 == rate2
    # Verify only one contract call was made
    assert price_reader.price_oracle_contract.functions.getPrice.call_count == 1

@pytest.mark.asyncio
async def test_price_validation_bounds(mock_sapphire_w3):
    """Test price validation with out-of-bounds values"""
    config = Mock()
    config.price_oracle_address = '0x1234567890abcdef1234567890abcdef12345678'
    config.price_oracle_abi = []
    config.slippage = 0.005
    
    # Mock contract returning invalid price (too high)
    contract = Mock()
    contract.functions.getPrice.return_value.call = AsyncMock(
        return_value=[20000000000000000000, 18, int(time.time())]  # 20 ROSE per USDC (too high)
    )
    mock_sapphire_w3.eth.contract.return_value = contract
    
    price_reader = PriceReader(config, mock_sapphire_w3)
    
    with pytest.raises(PriceValidationError):
        await price_reader.get_exchange_rate('USDC', 'ROSE')

@pytest.mark.asyncio
async def test_stale_price_detection(mock_sapphire_w3):
    """Test detection of stale price data"""
    config = Mock()
    config.price_oracle_address = '0x1234567890abcdef1234567890abcdef12345678'
    config.price_oracle_abi = []
    config.slippage = 0.005
    
    # Mock contract returning stale price (2 hours old)
    stale_timestamp = int(time.time()) - 7200
    contract = Mock()
    contract.functions.getPrice.return_value.call = AsyncMock(
        return_value=[500000000000000000, 18, stale_timestamp]
    )
    mock_sapphire_w3.eth.contract.return_value = contract
    
    price_reader = PriceReader(config, mock_sapphire_w3)
    
    with pytest.raises(PriceValidationError, match="Price data is stale"):
        await price_reader.get_exchange_rate('USDC', 'ROSE')

def test_calculate_output_amount(price_reader):
    """Test ROSE output amount calculation"""
    # 1 USDC (1,000,000 units) at rate 0.5 ROSE/USDC with 0.5% slippage
    input_amount = 1_000_000  # 1 USDC
    exchange_rate = Decimal('0.5')
    
    output = price_reader.calculate_output_amount(input_amount, exchange_rate)
    
    # Expected: 1 * 0.5 * 0.995 * 10^18 = 497,500,000,000,000,000
    expected = int(Decimal('1') * Decimal('0.5') * Decimal('0.995') * Decimal(10**18))
    assert output == expected

@pytest.mark.asyncio
async def test_contract_call_retry(mock_sapphire_w3):
    """Test contract call retry logic"""
    config = Mock()
    config.price_oracle_address = '0x1234567890abcdef1234567890abcdef12345678'
    config.price_oracle_abi = []
    config.slippage = 0.005
    
    # Mock contract that fails twice then succeeds
    call_count = 0
    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise Exception("RPC error")
        return [500000000000000000, 18, int(time.time())]
    
    contract = Mock()
    contract.functions.getPrice.return_value.call = mock_call
    mock_sapphire_w3.eth.contract.return_value = contract
    
    price_reader = PriceReader(config, mock_sapphire_w3)
    
    # Should succeed after retries
    rate = await price_reader.get_exchange_rate('USDC', 'ROSE')
    assert rate == Decimal('0.5')
    assert call_count == 3  # Failed twice, succeeded on third attempt
```

### 6.2 Integration Tests

```python
# tests/integration/test_price_oracle_integration.py
import pytest
from rofl_paymaster.oracle.price_reader import PriceReader
from rofl_paymaster.config import Config

@pytest.mark.integration
@pytest.mark.asyncio
async def test_price_oracle_contract_integration():
    """Test integration with actual price oracle contract on testnet"""
    # This test requires a deployed price oracle contract on testnet
    config = Config('config/test.yaml')
    
    # Create connection to Sapphire testnet
    sapphire_w3 = Web3(Web3.HTTPProvider(config.sapphire_rpc_urls[0]))
    
    # Initialize price reader
    price_reader = PriceReader(config, sapphire_w3)
    
    # Test price retrieval
    rate = await price_reader.get_exchange_rate('USDC', 'ROSE')
    
    # Verify rate is reasonable
    assert Decimal('0.01') <= rate <= Decimal('10.0')
    assert isinstance(rate, Decimal)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_oracle_status_monitoring():
    """Test price oracle status monitoring"""
    config = Config('config/test.yaml')
    sapphire_w3 = Web3(Web3.HTTPProvider(config.sapphire_rpc_urls[0]))
    price_reader = PriceReader(config, sapphire_w3)
    
    # Get oracle status
    status = await price_reader.get_oracle_status()
    
    # Verify status structure
    assert 'healthy' in status
    assert 'oracle_address' in status
    
    if status['healthy']:
        assert 'last_update' in status
        assert status['last_update'] > 0
```

## 7. Deployment Architecture

### 7.1 Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY pyproject.toml README.md ./
COPY src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN useradd --create-home --shell /bin/bash rofl

# Copy application from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/src /app/src

# Copy configuration and ABIs
COPY config/ /app/config/
COPY abis/ /app/abis/

WORKDIR /app

# Set ownership
RUN chown -R rofl:rofl /app

# Switch to non-root user
USER rofl

# Expose ports
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)"

# Default command
CMD ["python", "-m", "rofl_paymaster"]
```

## 8. Monitoring and Observability

### 8.1 Price Oracle Specific Metrics

```python
# Additional metrics for price oracle monitoring
price_oracle_calls = Counter(
    'rofl_price_oracle_calls_total',
    'Total price oracle contract calls',
    ['status']
)

price_oracle_response_time = Histogram(
    'rofl_price_oracle_response_time_seconds',
    'Price oracle contract call response time',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

price_deviation = Gauge(
    'rofl_price_deviation_percent',
    'Price deviation from cached value'
)

stale_price_alerts = Counter(
    'rofl_stale_price_alerts_total',
    'Alerts for stale price data'
)

emergency_rate_usage = Counter(
    'rofl_emergency_rate_usage_total',
    'Usage of emergency fallback rates'
)

class PriceOracleMetrics:
    """Metrics collection for price oracle operations"""
    
    @staticmethod
    def record_price_call(status: str, duration: float):
        """Record price oracle call metrics"""
        price_oracle_calls.labels(status=status).inc()
        price_oracle_response_time.observe(duration)
    
    @staticmethod
    def record_price_deviation(deviation_percent: float):
        """Record price deviation from cached value"""
        price_deviation.set(deviation_percent)
    
    @staticmethod
    def record_stale_price():
        """Record stale price detection"""
        stale_price_alerts.inc()
    
    @staticmethod
    def record_emergency_rate_usage():
        """Record usage of emergency rate"""
        emergency_rate_usage.inc()
```

### 8.2 Health Check Updates

```python
async def _check_price_oracle(self) -> Dict[str, Any]:
    """Check price oracle smart contract health"""
    try:
        start_time = time.time()
        
        # Test price oracle contract call
        status = await self.price_reader.get_oracle_status()
        
        call_duration = time.time() - start_time
        
        if status['healthy']:
            return {
                'healthy': True,
                'response_time': call_duration,
                'last_update': status.get('last_update', 0),
                'oracle_address': status['oracle_address']
            }
        else:
            return {
                'healthy': False,
                'error': status.get('error', 'Unknown error'),
                'oracle_address': status['oracle_address']
            }
            
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e),
            'oracle_address': self.config.price_oracle_address
        }
```

### 8.3 Updated Alert Rules

```yaml
# monitoring/alert_rules.yml
groups:
  - name: rofl_paymaster_alerts
    rules:
      - alert: PriceOracleDown
        expr: rofl_price_oracle_calls_total{status="failed"} > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Price oracle contract is failing"
          description: "Price oracle contract calls are failing"
      
      - alert: StalePriceData
        expr: rofl_stale_price_alerts_total > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Stale price data detected"
          description: "Price oracle is returning stale data"
      
      - alert: EmergencyRateInUse
        expr: rofl_emergency_rate_usage_total > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Emergency rate fallback activated"
          description: "Using emergency rates due to price oracle failure"
      
      - alert: HighPriceDeviation
        expr: rofl_price_deviation_percent > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High price deviation detected"
          description: "Price deviation is {{ $value }}%"
```

## 9. Future Enhancements

### 9.1 Advanced Price Oracle Features

```python
class MultiSourcePriceOracle:
    """Enhanced price oracle with multiple on-chain sources"""
    
    def __init__(self, config: Config, sapphire_w3: Web3):
        self.sapphire_w3 = sapphire_w3
        
        # Multiple price oracle contracts
        self.primary_oracle = sapphire_w3.eth.contract(
            address=config.primary_price_oracle_address,
            abi=config.price_oracle_abi
        )
        
        self.secondary_oracle = sapphire_w3.eth.contract(
            address=config.secondary_price_oracle_address,
            abi=config.price_oracle_abi
        )
        
        self.tertiary_oracle = sapphire_w3.eth.contract(
            address=config.tertiary_price_oracle_address,
            abi=config.price_oracle_abi
        )
    
    async def get_consensus_price(self, from_token: str, to_token: str) -> Decimal:
        """Get consensus price from multiple oracles"""
        prices = []
        
        # Query all oracles
        for oracle_name, oracle_contract in [
            ('primary', self.primary_oracle),
            ('secondary', self.secondary_oracle),
            ('tertiary', self.tertiary_oracle)
        ]:
            try:
                price_data = await oracle_contract.functions.getPrice(
                    from_token, to_token
                ).call()
                
                price = self._parse_price_data(price_data)
                prices.append((oracle_name, price))
                
            except Exception as e:
                logger.warning(f"Oracle {oracle_name} failed: {e}")
        
        if len(prices) < 2:
            raise PriceOracleError("Insufficient oracle responses for consensus")
        
        # Calculate consensus (median)
        price_values = [price for _, price in prices]
        consensus_price = statistics.median(price_values)
        
        # Check for outliers
        max_deviation = Decimal('0.05')  # 5%
        for oracle_name, price in prices:
            deviation = abs(price - consensus_price) / consensus_price
            if deviation > max_deviation:
                logger.warning(f"Oracle {oracle_name} deviates by {deviation:.2%}")
        
        return consensus_price

class TimeWeightedAveragePrice:
    """TWAP implementation for price smoothing"""
    
    def __init__(self, window_size: int = 300):  # 5 minutes
        self.window_size = window_size
        self.price_history = deque()
    
    def add_price_point(self, price: Decimal, timestamp: int):
        """Add price point to history"""
        self.price_history.append((timestamp, price))
        
        # Remove old points outside window
        cutoff_time = timestamp - self.window_size
        while (self.price_history and 
               self.price_history[0][0] < cutoff_time):
            self.price_history.popleft()
    
    def get_twap(self) -> Decimal:
        """Calculate time-weighted average price"""
        if len(self.price_history) < 2:
            return self.price_history[-1][1] if self.price_history else Decimal('0')
        
        total_weighted_price = Decimal('0')
        total_time = Decimal('0')
        
        for i in range(1, len(self.price_history)):
            prev_time, prev_price = self.price_history[i-1]
            curr_time, _ = self.price_history[i]
            
            time_weight = Decimal(curr_time - prev_time)
            total_weighted_price += prev_price * time_weight
            total_time += time_weight
        
        return total_weighted_price / total_time if total_time > 0 else Decimal('0')
```

## 10. Conclusion

This updated design document reflects the architecture for the ROFL Cross-Chain Paymaster system with an on-chain price oracle:

1. **Simplified Price Architecture**: Removes external API dependencies in favor of reading from a deployed smart contract on Sapphire
2. **Enhanced Reliability**: Smart contract-based price oracle provides more reliable and manipulation-resistant pricing
3. **Improved Security**: On-chain price data reduces external attack vectors and API key management
4. **Better Integration**: Direct integration with Sapphire ecosystem through smart contract calls
5. **Future-Ready**: Architecture supports multiple price oracles and advanced features like TWAP

The key changes from the original design:
- **Price Reader** replaces the multi-source API price oracle
- **Contract-based pricing** with validation and caching
- **Simplified error handling** for price operations
- **Enhanced monitoring** for smart contract interactions
- **Reduced external dependencies** and configuration complexity

The system maintains all security, reliability, and performance requirements while providing a more streamlined and blockchain-native approach to price discovery. The integration with the liquefaction submodule's `ITrivalBlockHashOracle` interface ensures compatibility with the broader Oasis ecosystem.