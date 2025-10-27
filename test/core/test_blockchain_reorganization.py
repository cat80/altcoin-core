import unittest
import os
import shutil
import time
import sys

from core.blockchain import Blockchain
from core.block import Block, BlockHeader
from core.block_validator import BlockValidator
from core.transaction import Transaction, TxIn, TxOut
from utils import MerkleTree
from config import INITIAL_BLOCK_REWARD, BLOCK_STATUS_VALID, BLOCK_STATUS_INVALID
import dataclasses


class StateDbBatchProxy():
    """
        dbbatch的代理追踪类
    """
    def put(self,key,value):
        pass
    def delete(self,key):
        pass


class TestBlockchainReorganization(unittest.TestCase):

    def setUp(self):
        """Set up a temporary data directory and a new blockchain for each test."""
        self.test_dir = "test_reorg_integration1"
        # Clean up any previous runs
        # if os.path.exists(self.test_dir):
        #     shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir,exist_ok=True)
        
        self.blockchain = Blockchain.new_from_data_dir(self.test_dir)

    def tearDown(self):
        """Clean up the temporary data directory after each test."""
        self.blockchain.close()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_next_block(self, prev_header: BlockHeader, coinbase_data: bytes,block_height) -> Block:
        """Helper function to create a valid block on top of a previous one."""
        coinbase_unlcking_script_prefix = str(block_height).encode('utf-8') + b':'
        coinbase_data = coinbase_unlcking_script_prefix + coinbase_data
        coinbase_tx = Transaction(1, [TxIn.create_coinbase_txin(coinbase_data)], [TxOut(INITIAL_BLOCK_REWARD, b'')],lock_time=0)
        
        # In a real scenario, we'd add more transactions and calculate fees.
        # For this test, coinbase is sufficient.
        transactions = [coinbase_tx]
        tx_hashes = [tx.hash() for tx in transactions]
        merkle_root = MerkleTree(tx_hashes).root
        prev_header_info = self.blockchain.block_index.get_header_info(prev_header.hash())
        bits = self.blockchain.block_index.calculate_required_bits(prev_header_info['height']+1)
        header = BlockHeader(
            version=1,
            prev_block_hash=prev_header.hash(),
            merkle_root=merkle_root,
            timestamp=int(time.time()),
            bits=bits,
            nonce=0
        )
        
        # Mine the block (find a valid nonce)
        target = BlockValidator.bits_to_target(bits)
        while  int.from_bytes(header.hash(), 'big') >= target: # Simplified mining
            # header.nonce += 1
            header = dataclasses.replace(header, nonce=header.nonce + 1)
        return Block(header, transactions)

    def test_reorganization_to_longer_chain(self):
        """
        Tests a full chain reorganization scenario:
        1. Build a main chain: G -> A -> B
        2. Build a fork from A: A -> C -> D
        3. Adding D should trigger a reorg, making G -> A -> C -> D the main chain.
        """
        # --- 1. Build initial main chain: G -> A -> B ---
        
        genesis_tip = self.blockchain.get_best_tip()
        self.assertIsNotNone(genesis_tip)

        genesis_tip['version'] = 1
        # Create and add block A

        block_a = self.create_next_block(BlockHeader.from_dict(genesis_tip), b'Block A',genesis_tip['height']+1)
        self.assertTrue(self.blockchain.add_block(block_a))
        tip_a_info = self.blockchain.get_best_tip()
        self.assertEqual(tip_a_info['block_hash'], block_a.hash())
        
        # Create and add block B
        block_b = self.create_next_block(block_a.header, b'Block B',genesis_tip['height']+2)
        self.assertTrue(self.blockchain.add_block(block_b))
        tip_b_info = self.blockchain.get_best_tip()
        self.assertEqual(tip_b_info['block_hash'], block_b.hash())
        
        # --- 2. Verify initial state ---
        
        # Check that block B's coinbase UTXO exists
        coinbase_b_tx = block_b.transactions[0]
        utxo_b_input = TxIn(prev_tx_hash=coinbase_b_tx.hash(), prev_tx_out_index=0,unlocking_script=b'aa')
        utxo_b = self.blockchain.chain_state.get_utxo(utxo_b_input)
        self.assertIsNotNone(utxo_b)
        self.assertEqual(utxo_b.value, INITIAL_BLOCK_REWARD)
        
        # --- 3. Create the fork ---
        
        # Create block C (forks from A)
        block_c = self.create_next_block(block_a.header, b'Block Cass',genesis_tip['height']+2)
        print(f'add block c ,onnce:{block_c.header.nonce},hash is :{block_c.hash().hex()}')
        self.assertTrue(self.blockchain.add_block(block_c))
        
        # The tip should STILL be B, as the new chain is not longer/heavier yet
        current_tip = self.blockchain.get_best_tip()
        self.assertEqual(current_tip['block_hash'], block_b.hash())
        
        # Create block D (extends the C chain)
        block_d = self.create_next_block(block_c.header, b'Block D',genesis_tip['height']+3)
        
        # This should trigger the reorganization
        self.assertTrue(self.blockchain.add_block(block_d))
        
        # --- 4. Verify the final state after reorganization ---
        
        # a. The new tip should be D
        final_tip = self.blockchain.get_best_tip()

        self.assertEqual(final_tip['block_hash'], block_d.hash())
        
        # b. Check block statuses in the index
        info_b = self.blockchain.block_index.get_header_info(block_b.hash())
        info_c = self.blockchain.block_index.get_header_info(block_c.hash())
        info_d = self.blockchain.block_index.get_header_info(block_d.hash())
        
        self.assertEqual(info_b['status'], BLOCK_STATUS_INVALID) # B is no longer on the main chain
        self.assertEqual(info_c['status'], BLOCK_STATUS_VALID)   # C is now on the main chain
        self.assertEqual(info_d['status'], BLOCK_STATUS_VALID)   # D is the new tip

        print(f'info a coinbase tx hash:{block_a.transactions[0].hash().hex()}')
        print(f'info b coinbase tx hash:{block_b.transactions[0].hash().hex()}')
        print(f'info c coinbase tx hash:{block_c.transactions[0].hash().hex()}')
        print(f'info d coinbase tx hash:{block_d.transactions[0].hash().hex()}')
        # c. Verify UTXO state
        # Block B's coinbase UTXO should have been rolled back (does not exist)
        utxo_b_after_reorg = self.blockchain.chain_state.get_utxo(utxo_b_input)
        # 修复 回滚的block的coinbase的utxo仍然有效。解决coinbase 交易的hash冲突的问题。
        self.assertIsNone(utxo_b_after_reorg)
        
        # Block D's coinbase UTXO should now exist
        coinbase_d_tx = block_d.transactions[0]
        utxo_d_input = TxIn(prev_tx_hash=coinbase_d_tx.hash(), prev_tx_out_index=0,unlocking_script=b'')
        utxo_d_after_reorg = self.blockchain.chain_state.get_utxo(utxo_d_input)
        self.assertIsNotNone(utxo_d_after_reorg)
        self.assertEqual(utxo_d_after_reorg.value, INITIAL_BLOCK_REWARD)

if __name__ == '__main__':
    unittest.main()
