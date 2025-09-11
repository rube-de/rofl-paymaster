"""
Test proof generation against TypeScript reference implementation.

This test ensures that the Python proof generation matches the TypeScript
implementation byte-for-byte, which is critical for cross-chain verification.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from web3 import Web3
from src.rofl_relayer.proof_manager import ProofManager
from src.rofl_relayer.utils.contract_utility import ContractUtility
from src.rofl_relayer.event_processor import PingEvent


async def test_proof_matches_typescript():
    """
    Test that Python proof generation matches TypeScript proof.json.
    """
    print("🧪 Testing proof generation against TypeScript reference")
    
    # Load TypeScript proof for comparison
    proof_path = Path(__file__).parent.parent.parent / "ping" / "proof.json"
    if not proof_path.exists():
        print(f"❌ TypeScript proof not found at {proof_path}")
        print("   Please run 'bunx hardhat generate-proof' first in the ping package")
        return False
        
    with open(proof_path) as f:
        typescript_proof = json.load(f)
        
    print(f"📋 TypeScript proof loaded from {proof_path}")
    print(f"   Chain ID: {typescript_proof[0]}")
    print(f"   Block Number: {typescript_proof[1]}")
    print(f"   Log Index: {typescript_proof[7]}")
    
    # Extract transaction details from proof
    # The proof.json doesn't contain tx hash, so we need to get it from env or hardcode
    # For testing, we'll use the known transaction from the proof
    # Updated to use the newer transaction
    tx_hash = "0x9b1003047adc2a6a1f0c4fb5398ee40108097f4a1716684af1d4e77d21603546"
    expected_log_index = typescript_proof[7]  # Log index from proof
    
    # Initialize Web3 connection to source chain
    source_rpc = os.environ.get("SOURCE_RPC_URL", "https://ethereum-sepolia.publicnode.com")
    print(f"\n🌐 Connecting to source chain: {source_rpc}")
    
    web3_source = Web3(Web3.HTTPProvider(source_rpc))
    if not web3_source.is_connected():
        print("❌ Failed to connect to source chain")
        return False
    
    # Get transaction receipt to extract Ping event details
    print(f"📥 Fetching transaction receipt to get Ping event details...")
    receipt = web3_source.eth.get_transaction_receipt(tx_hash)
    if not receipt:
        print("❌ Transaction receipt not found")
        return False
    
    # Find the Ping event in the logs
    # Ping event signature: Ping(address,uint256)
    ping_topic = Web3.keccak(text="Ping(address,uint256)")
    sender = None
    event_block_number = None
    
    for log in receipt['logs']:
        if len(log['topics']) >= 3 and log['topics'][0] == ping_topic:
            # Extract sender from topics[1] (remove padding)
            sender_bytes = log['topics'][1][-20:]  # Last 20 bytes is the address
            sender = Web3.to_checksum_address(sender_bytes)
            # Extract block number from topics[2]
            event_block_number = int.from_bytes(log['topics'][2], 'big')
            print(f"   Found Ping event - Sender: {sender}, Block: {event_block_number}")
            break
    
    if not sender:
        print("❌ Ping event not found in transaction")
        return False
        
    # Initialize utilities
    # Use a dummy RPC for ContractUtility since we only need ABI loading
    contract_util = ContractUtility(rpc_url="http://localhost:8545")  # Dummy URL for ABI-only mode
    
    # Create ProofManager
    proof_manager = ProofManager(
        w3_source=web3_source,
        contract_util=contract_util,
        rofl_util=None  # Testing without ROFL
    )
    
    # Create PingEvent object for proof generation
    ping_event = PingEvent(
        tx_hash=tx_hash,
        block_number=event_block_number,
        sender=sender,
        timestamp=receipt['blockNumber'],  # Using block number as timestamp for testing
        ping_id=f"ping_{tx_hash[:8]}"  # Generate a test ping_id
    )
    
    # Generate proof with PingEvent object
    print(f"\n🔮 Generating proof for transaction {tx_hash}")
    print(f"   Using sender: {sender}, block: {event_block_number}")
    try:
        python_proof = await proof_manager.generate_proof(ping_event)
        print("✅ Proof generated successfully")
    except Exception as e:
        print(f"❌ Failed to generate proof: {e}")
        return False
        
    # Compare proofs
    print("\n📊 Comparing Python and TypeScript proofs:")
    
    # Compare each element
    elements = [
        "Chain ID",
        "Block Number", 
        "Encoded Block Header",
        "Ancestral Block Number",
        "Ancestral Block Headers",
        "Merkle Proof",
        "Transaction Index",
        "Log Index"
    ]
    
    all_match = True
    for i, element_name in enumerate(elements):
        python_val = python_proof[i]
        typescript_val = typescript_proof[i]
        
        # Special handling for arrays and hex strings
        if isinstance(python_val, list) and isinstance(typescript_val, list):
            # Compare arrays element by element
            if len(python_val) != len(typescript_val):
                print(f"❌ {element_name}: Length mismatch (Python: {len(python_val)}, TypeScript: {len(typescript_val)})")
                all_match = False
            else:
                # Compare each element, normalizing hex strings
                match = all([
                    normalize_hex(p) == normalize_hex(t) 
                    for p, t in zip(python_val, typescript_val)
                ])
                if match:
                    print(f"✅ {element_name}: Match ({len(python_val)} elements)")
                else:
                    print(f"❌ {element_name}: Content mismatch")
                    all_match = False
        else:
            # Compare single values, normalizing hex strings
            python_normalized = normalize_hex(python_val)
            typescript_normalized = normalize_hex(typescript_val)
            
            if python_normalized == typescript_normalized:
                if isinstance(python_val, str) and len(python_val) > 20:
                    print(f"✅ {element_name}: Match ({python_normalized[:10]}...)")
                else:
                    print(f"✅ {element_name}: Match ({python_normalized})")
            else:
                print(f"❌ {element_name}: Mismatch")
                if isinstance(python_val, str) and len(str(python_val)) > 50:
                    print(f"   Python:     {str(python_normalized)[:50]}...")
                    print(f"   TypeScript: {str(typescript_normalized)[:50]}...")
                else:
                    print(f"   Python:     {python_normalized}")
                    print(f"   TypeScript: {typescript_normalized}")
                all_match = False
                
    # Final result
    print("\n" + "=" * 50)
    if all_match:
        print("🎉 SUCCESS: Python proof matches TypeScript exactly!")
        return True
    else:
        print("❌ FAILURE: Proofs do not match")
        print("\nDebug information:")
        print(f"Python proof length: {len(str(python_proof))}")
        print(f"TypeScript proof length: {len(str(typescript_proof))}")
        return False


def normalize_hex(value):
    """
    Normalize hex strings for comparison.
    
    Args:
        value: Value to normalize
        
    Returns:
        Normalized value for comparison
    """
    if isinstance(value, str) and value.startswith("0x"):
        # Remove 0x prefix and convert to lowercase
        return value[2:].lower()
    elif isinstance(value, bytes):
        return value.hex().lower()
    elif isinstance(value, list):
        return [normalize_hex(v) for v in value]
    else:
        return value


async def test_proof_generation_errors():
    """
    Test error handling in proof generation.
    """
    print("\n🧪 Testing error handling")
    
    # Initialize Web3 connection
    source_rpc = os.environ.get("SOURCE_RPC_URL", "https://ethereum-sepolia.publicnode.com")
    web3_source = Web3(Web3.HTTPProvider(source_rpc))
    
    if not web3_source.is_connected():
        print("⚠️  Skipping error tests - no connection to source chain")
        return
        
    # Initialize ProofManager
    contract_util = ContractUtility()
    proof_manager = ProofManager(
        w3_source=web3_source,
        contract_util=contract_util,
        rofl_util=None  # Testing without ROFL
    )
    
    # Test with invalid transaction hash
    print("\n📍 Testing with invalid transaction hash...")
    try:
        invalid_event = PingEvent(
            tx_hash="0xinvalid",
            block_number=0,
            sender="0x0000000000000000000000000000000000000000",
            timestamp=0,
            ping_id="invalid"
        )
        await proof_manager.generate_proof(invalid_event)
        print("❌ Should have raised an error for invalid hash")
    except Exception as e:
        print(f"✅ Correctly raised error: {type(e).__name__}")
        
    # Test with non-existent transaction
    print("\n📍 Testing with non-existent transaction...")
    try:
        fake_hash = "0x" + "0" * 64
        fake_event = PingEvent(
            tx_hash=fake_hash,
            block_number=0,
            sender="0x0000000000000000000000000000000000000000",
            timestamp=0,
            ping_id="fake"
        )
        await proof_manager.generate_proof(fake_event)
        print("❌ Should have raised an error for non-existent tx")
    except Exception as e:
        print(f"✅ Correctly raised error: {type(e).__name__}")
        
    print("\n✅ Error handling tests completed")


async def main():
    """
    Run all proof generation tests.
    """
    print("=" * 50)
    print("PROOF GENERATION TEST SUITE")
    print("=" * 50)
    
    # Run main compatibility test
    success = await test_proof_matches_typescript()
    
    # Run error handling tests
    await test_proof_generation_errors()
    
    # Summary
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)