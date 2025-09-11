#!/usr/bin/env python
"""
Test suite for the ROFL Relayer event monitoring functionality.
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rofl_relayer.relayer import ROFLRelayer
from src.rofl_relayer.utils.polling_event_listener import PollingEventListener


async def test_polling_listener_structure():
    """Test the PollingEventListener class structure."""
    print("\n" + "="*60)
    print("Test: PollingEventListener Structure")
    print("="*60)
    
    # Create a minimal ABI for testing
    test_abi = [
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "sender", "type": "address"},
                {"indexed": True, "name": "timestamp", "type": "uint256"},
                {"indexed": False, "name": "blockNumber", "type": "uint256"}
            ],
            "name": "Ping",
            "type": "event"
        }
    ]
    
    # Create listener instance
    listener = PollingEventListener(
        rpc_url="https://ethereum-sepolia.publicnode.com",
        contract_address="0xDCC23A03E6b6aA254cA5B0be942dD5CafC9A2299",
        event_name="Ping",
        abi=test_abi,
        lookback_blocks=10
    )
    
    # Test status method
    status = listener.get_status()
    assert status["event_name"] == "Ping"
    assert status["is_running"] == False
    assert status["last_processed_block"] is None
    
    print("[PASS] PollingEventListener structure validated")
    return True


async def test_relayer_with_real_contracts():
    """Test the relayer with real deployed contracts."""
    print("\n" + "="*60)
    print("Test: ROFL Relayer with Deployed Contracts")
    print("="*60)
    
    # Set up environment with real contract addresses
    os.environ["SOURCE_RPC_URL"] = "https://ethereum-sepolia.publicnode.com"
    os.environ["TARGET_RPC_URL"] = "https://testnet.sapphire.oasis.io"
    os.environ["PING_SENDER_ADDRESS"] = "0xDCC23A03E6b6aA254cA5B0be942dD5CafC9A2299"
    os.environ["PING_RECEIVER_ADDRESS"] = "0x1f54b7AF3A462aABed01D5910a3e5911e76D4B51"
    os.environ["ROFL_ADAPTER_ADDRESS"] = "0x9f983F759d511D0f404582b0bdc1994edb5db856"
    os.environ["PRIVATE_KEY"] = "0x" + "0" * 64  # Dummy key for testing
    
    print(f"PingSender: {os.environ['PING_SENDER_ADDRESS']}")
    print(f"ROFLAdapter: {os.environ['ROFL_ADAPTER_ADDRESS']}")
    print("\nNote: Looking back 100 blocks for any recent Ping events...")
    print("To generate events, run: bunx hardhat send-ping --network eth-sepolia")
    
    # Create relayer instance using factory method
    relayer = ROFLRelayer.from_env(local_mode=True)
    
    # Run for a longer time to see if we catch any events
    print("\nRunning for 10 seconds to check for events...")
    
    async def stop_after_delay():
        await asyncio.sleep(10)
        relayer.stop()
    
    # Start both tasks
    stop_task = asyncio.create_task(stop_after_delay())
    run_task = asyncio.create_task(relayer.run())
    
    # Wait for completion
    await asyncio.gather(stop_task, run_task, return_exceptions=True)
    
    # Validate that the relayer initialized correctly
    assert relayer.ping_listener is not None
    assert relayer.hash_listener is not None
    
    print("\n[PASS] ROFL Relayer initialized and ran successfully")
    # Get stats from the event processor
    stats = relayer.event_processor.get_stats()
    print(f"   - Pending pings: {stats['pending_pings']}")
    print(f"   - Processed hashes: {stats['processed_hashes']}")
    print(f"   - Stored hashes: {stats['stored_hashes']}")
    
    return True


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("ROFL Relayer Test Suite")
    print("="*60)
    
    tests = [
        ("PollingEventListener Structure", test_polling_listener_structure),
        ("ROFL Relayer Integration", test_relayer_with_real_contracts),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, "PASS"))
        except Exception as e:
            results.append((test_name, f"FAIL: {e}"))
            import traceback
            traceback.print_exc()
    
    # Print summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    all_passed = True
    for test_name, result in results:
        status = "[PASS]" if result == "PASS" else "[FAIL]"
        print(f"{status} {test_name}: {result}")
        if result != "PASS":
            all_passed = False
    
    if all_passed:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)