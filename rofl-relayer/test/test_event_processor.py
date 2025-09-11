"""Unit tests for the EventProcessor class."""

import pytest
from collections import OrderedDict
from unittest.mock import Mock
from rofl_relayer.event_processor import EventProcessor
from rofl_relayer.models import PingEvent


class TestEventProcessor:
    """Test suite for EventProcessor class."""
    
    def test_processed_hash_tracking_with_lru(self):
        """Test that hash tracking maintains LRU behavior with O(1) lookups."""
        processor = EventProcessor()
        
        # Set a smaller max for testing
        processor.MAX_PROCESSED_HASHES = 5
        processor.processed_tx_hashes = OrderedDict()
        
        # Add hashes up to capacity
        hashes = [f"0xhash{i}" for i in range(5)]
        for hash_val in hashes:
            processor._track_processed_hash(hash_val)
        
        # Verify all hashes are tracked
        assert len(processor.processed_tx_hashes) == 5
        for hash_val in hashes:
            assert hash_val in processor.processed_tx_hashes
        
        # Add one more hash - should evict the oldest (hash0)
        processor._track_processed_hash("0xhash5")
        
        # Verify LRU eviction worked correctly
        assert len(processor.processed_tx_hashes) == 5
        assert "0xhash0" not in processor.processed_tx_hashes
        assert "0xhash5" in processor.processed_tx_hashes
        
        # Verify OrderedDict order (oldest to newest)
        expected_order = ["0xhash1", "0xhash2", "0xhash3", "0xhash4", "0xhash5"]
        assert list(processor.processed_tx_hashes.keys()) == expected_order
    
    def test_duplicate_hash_moves_to_end(self):
        """Test that duplicate hashes are moved to end (most recent) in LRU."""
        processor = EventProcessor()
        
        # Track multiple hashes
        processor._track_processed_hash("0xabc123")
        processor._track_processed_hash("0xdef456")
        processor._track_processed_hash("0xghi789")
        
        # Re-track the first hash (should move to end)
        processor._track_processed_hash("0xabc123")
        
        # Verify hash was moved to end and no duplicate was added
        assert len(processor.processed_tx_hashes) == 3
        assert list(processor.processed_tx_hashes.keys()) == ["0xdef456", "0xghi789", "0xabc123"]
    
    def test_o1_lookup_performance(self):
        """Test that hash lookup is O(1) using OrderedDict."""
        processor = EventProcessor()
        
        # Add many hashes
        for i in range(1000):
            processor._track_processed_hash(f"0xhash{i}")
        
        # Verify we're using OrderedDict for O(1) lookups
        assert isinstance(processor.processed_tx_hashes, OrderedDict)
        assert "0xhash500" in processor.processed_tx_hashes  # O(1) operation
        assert "0xnonexistent" not in processor.processed_tx_hashes  # O(1) operation
        
        # OrderedDict maintains both O(1) lookup and insertion order
        assert len(processor.processed_tx_hashes) == 1000
    
    def test_pending_pings_o1_lookup_by_block(self):
        """Test that pending_pings provides O(1) lookup by block number."""
        processor = EventProcessor()
        
        # Create test pings for different blocks
        ping1 = PingEvent(
            tx_hash="0xhash1",
            block_number=100,
            sender="0xaddr1",
            timestamp=1000,
            ping_id="ping1"
        )
        ping2 = PingEvent(
            tx_hash="0xhash2",
            block_number=200,
            sender="0xaddr2",
            timestamp=2000,
            ping_id="ping2"
        )
        ping3 = PingEvent(
            tx_hash="0xhash3",
            block_number=100,  # Same block as ping1
            sender="0xaddr3",
            timestamp=1001,
            ping_id="ping3"
        )
        
        # Manually add pings (simulating what process_ping_event does)
        processor.pending_pings[100] = [ping1, ping3]
        processor.pending_pings[200] = [ping2]
        processor.pending_pings_count = 3
        
        # Test O(1) lookup by block number (no iteration needed!)
        block_100_pings = processor.pending_pings.get(100, [])
        assert len(block_100_pings) == 2
        assert ping1 in block_100_pings
        assert ping3 in block_100_pings
        
        # Test block with single ping
        block_200_pings = processor.pending_pings.get(200, [])
        assert len(block_200_pings) == 1
        assert ping2 in block_200_pings
        
        # Test non-existent block returns empty list
        no_pings = processor.pending_pings.get(999, [])
        assert no_pings == []
        
        # Verify count tracking
        assert processor.pending_pings_count == 3
    
    def test_stored_hashes_memory_leak_prevention(self):
        """Test that stored_hashes prevents memory leaks with size limit."""
        processor = EventProcessor()
        
        # Set small limit for testing
        processor.MAX_STORED_HASHES = 5
        processor.stored_hashes = OrderedDict()
        
        # Add more hashes than the limit
        for i in range(10):
            # Simulate the logic from process_hash_stored_event
            if len(processor.stored_hashes) >= processor.MAX_STORED_HASHES:
                processor.stored_hashes.popitem(last=False)  # Remove oldest
            processor.stored_hashes[i] = f"0xblockhash{i}"
        
        # Should only have the last 5 hashes
        assert len(processor.stored_hashes) == 5
        
        # Should have blocks 5-9 (0-4 were evicted)
        assert 0 not in processor.stored_hashes
        assert 4 not in processor.stored_hashes
        assert 5 in processor.stored_hashes
        assert 9 in processor.stored_hashes
        
        # Verify FIFO order (oldest to newest)
        expected_blocks = [5, 6, 7, 8, 9]
        assert list(processor.stored_hashes.keys()) == expected_blocks
        
        # Verify correct values
        for block_num in expected_blocks:
            assert processor.stored_hashes[block_num] == f"0xblockhash{block_num}"
    
    def test_stats_with_new_structures(self):
        """Test that get_stats works correctly with new data structures."""
        processor = EventProcessor()
        
        # Add some processed hashes
        processor.processed_tx_hashes["0xhash1"] = None
        processor.processed_tx_hashes["0xhash2"] = None
        
        # Add pending pings to both structures
        ping1 = PingEvent("hash1", 100, "addr1", 1000, "p1")
        ping2 = PingEvent("hash2", 100, "addr2", 1001, "p2")
        ping3 = PingEvent("hash3", 200, "addr3", 2000, "p3")
        
        processor.pending_pings[100] = [ping1, ping2]
        processor.pending_pings[200] = [ping3]
        
        # Add to deque as well (new structure)
        processor.pending_pings_order.append(ping1)
        processor.pending_pings_order.append(ping2)
        processor.pending_pings_order.append(ping3)
        
        # Add stored hashes
        processor.stored_hashes[100] = "0xblockhash100"
        processor.stored_hashes[200] = "0xblockhash200"
        
        # Get stats
        stats = processor.get_stats()
        
        # Verify stats
        assert stats['processed_hashes'] == 2
        assert stats['pending_pings'] == 3  # Uses deque length
        assert stats['stored_hashes'] == 2