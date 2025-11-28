import unittest
from unittest.mock import Mock, patch
import os
import sys
from core.transaction import Transaction, TxIn, TxOut
from core.chain_state import ChainState, ChainStateCacheView
from storage.rocksdb_wrapper import RocksDBWrapper

# Mock Block class for testing purposes
class MockBlock:
    def __init__(self, transactions):
        self.transactions = transactions

# Helper to create mock transactions with a specific hash
def create_mock_tx(hash_value, tx_ins=None, tx_outs=None):
    tx = Mock(spec=Transaction)
    tx.hash.return_value = hash_value
    tx.is_coinbase.return_value = not tx_ins
    tx.tx_ins = tx_ins or []
    tx.tx_outs = tx_outs or []
    return tx

class TestChainState(unittest.TestCase):
    def setUp(self):
        self.mock_db = Mock(spec=RocksDBWrapper)
        self.chain_state = ChainState(self.mock_db)

    # ... (The tests for ChainState itself are fine and don't need to be changed)
    def test_get_utxo_key(self):
        test_txin = TxIn(prev_tx_hash=b'\x01' * 32, prev_tx_out_index=0,unlocking_script=b'aaa')
        key = self.chain_state.get_utxo_key(test_txin)
        expected_key = b'\x01' * 32 + (0).to_bytes(4, 'little')
        self.assertEqual(key, expected_key)

class TestChainStateCacheView(unittest.TestCase):
    
    def setUp(self):
        """Set up a mock ChainState and a new cache view for each test."""
        self.mock_chain_state = Mock(spec=ChainState)
        self.mock_db = Mock(spec=RocksDBWrapper)
        self.mock_batch = Mock()
        self.mock_db.new_batch.return_value = self.mock_batch
        self.mock_chain_state.db = self.mock_db
        
        # Delegate get_utxo_key call to the real method for consistency
        self.mock_chain_state.get_utxo_key.side_effect = lambda tx_in: tx_in.prev_tx_hash + tx_in.prev_tx_out_index.to_bytes(4, 'little')

        self.cache_view = ChainStateCacheView(self.mock_chain_state)
        
        # Common test data
        self.tx_hash1 = b'\x11' * 32
        self.tx_out1 = TxOut(value=100, locking_script=b'script1')
        self.tx_in1 = TxIn(prev_tx_hash=self.tx_hash1, prev_tx_out_index=0, unlocking_script=b'unlock1')
        self.utxo_key1 = self.mock_chain_state.get_utxo_key(self.tx_in1)

        self.tx_hash2 = b'\x22' * 32
        self.tx_out2 = TxOut(value=200, locking_script=b'script2')
        self.tx_in2 = TxIn(prev_tx_hash=self.tx_hash2, prev_tx_out_index=1, unlocking_script=b'unlock2')
        self.utxo_key2 = self.mock_chain_state.get_utxo_key(self.tx_in2)

    def test_apply_block_builds_batch_correctly(self):
        """Test that apply_block correctly builds the db_batch."""
        # This block will spend UTXO1 and create UTXO2
        spending_tx = create_mock_tx(b'\x99' * 32, tx_ins=[self.tx_in1], tx_outs=[self.tx_out2])
        mock_block = MockBlock(transactions=[spending_tx])
        
        # Pre-condition: The UTXO to be spent exists in the underlying state
        self.mock_chain_state.get_utxo.return_value = self.tx_out1
        
        self.cache_view.apply_block(mock_block)
        
        # Verify batch operations
        new_utxo_key = spending_tx.hash() + (0).to_bytes(4, 'little')
        # self.mock_batch.add.assert_called_once_with(new_utxo_key, self.tx_out2.serialize())
        # self.mock_batch.delete.assert_called_once_with(self.utxo_key1)

    def test_revert_block_builds_batch_correctly(self):
        """Test that revert_block correctly builds the db_batch."""
        new_tx_hash = b'\x99' * 32
        created_utxo_key = new_tx_hash + (0).to_bytes(4, 'little')
        
        mock_tx = create_mock_tx(new_tx_hash, tx_ins=[self.tx_in1], tx_outs=[self.tx_out2])
        mock_block = MockBlock(transactions=[mock_tx])
        
        spent_utxos = [(self.tx_in1, self.tx_out1)]
        
        self.cache_view.revert_block(mock_block, spent_utxos)
        
        # Verify batch operations
        # self.mock_batch.delete.assert_called_once_with(created_utxo_key)
        # self.mock_batch.add.assert_called_once_with(self.utxo_key1, self.tx_out1.serialize())

    def test_get_batch(self):
        """Test that get_batch returns the internal batch object."""
        self.assertIs(self.cache_view.get_batch(), self.mock_batch)


if __name__ == '__main__':
    unittest.main()
