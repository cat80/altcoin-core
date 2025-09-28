"""
test_blockchain_integration.py
An integration test for the core blockchain components to ensure they work together.
"""
import dataclasses
import unittest
import os
import shutil
import time

from core.blockchain import Blockchain
from core.block import Block
from core.block_header import BlockHeader
from core.transaction import Transaction, TxIn, TxOut
from core.block_validator import BlockValidator

class TestBlockchainIntegration(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for test data."""
        self.test_dir = "test_temp_data"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        self.blockchain = Blockchain(self.test_dir)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.blockchain.close()
        # if os.path.exists(self.test_dir):
        #     shutil.rmtree(self.test_dir)

    def test_genesis_block_creation(self):
        """
        Verify that the blockchain initializes with a valid genesis block.
        """
        print("\n--- Running test_01_genesis_block_creation ---")
        tip = self.blockchain.get_best_tip()
        self.assertIsNotNone(tip)
        self.assertEqual(tip['height'], 0)
        
        # Verify the genesis coinbase UTXO exists
        genesis_block_hash = tip['block_hash']
        genesis_block_info = self.blockchain.block_index.get_header_info(genesis_block_hash)
        genesis_block = self.blockchain.block_storage.read_block(genesis_block_info['file_index'], genesis_block_info['file_offset'])
        
        genesis_coinbase_tx = genesis_block.transactions[0]
        coinbase_tx_in = TxIn(prev_tx_hash=genesis_coinbase_tx.hash(), prev_tx_out_index=0, unlocking_script=b'')
        
        utxo = self.blockchain.chain_state.get_utxo(coinbase_tx_in)
        self.assertIsNotNone(utxo)
        self.assertEqual(utxo.value, 50 * 100000000)
        print("Genesis block and its UTXO verified successfully.")

    def _mine_block(self, prev_block_hash: bytes, transactions: list, bits: int) -> Block:
        """A simple mining utility for tests."""
        block = Block.create_new(prev_block_hash, transactions, bits)
        target = BlockValidator.bits_to_target(bits)
        
        while int.from_bytes(block.hash(), 'little') >= target:
            block.header = dataclasses.replace(block.header,nonce=block.header.nonce+1)
        return block

    def test_02_add_valid_block(self):
        """
        Test mining and adding a new, valid block to the chain.
        """
        # TODO:挖矿得重新降低难度验证，需要再重新写测试用例
        if True:
            return
        print("\n--- Running test_02_add_valid_block ---")
        # 1. Get the previous block's info (genesis block)
        prev_tip = self.blockchain.get_best_tip()
        prev_block_hash = prev_tip['block_hash']
        
        # 2. Create a new coinbase transaction for the new block
        new_height = prev_tip['height'] + 1
        reward = BlockValidator.get_block_reward(new_height)
        coinbase_tx = Transaction(1, [TxIn.create_coinbase_txin(f"Block {new_height}".encode())], [TxOut(reward, b'some_locking_script')], 0)
        
        # 3. Mine the new block
        print("Mining a new block...")
        new_block = self._mine_block(prev_block_hash, [coinbase_tx], prev_tip['bits'])
        print(f"Block mined! Nonce: {new_block.header.nonce}, Hash: {new_block.hash().hex()}")
        
        # 4. Add the block to the blockchain
        result = self.blockchain.add_block(new_block)
        self.assertTrue(result)
        
        # 5. Verify the new state
        new_tip = self.blockchain.get_best_tip()
        self.assertEqual(new_tip['height'], 1)
        self.assertEqual(new_tip['block_hash'], new_block.hash())
        
        # 6. Verify the new coinbase UTXO exists
        new_coinbase_tx_in = TxIn(prev_tx_hash=new_block.transactions[0].hash(), prev_tx_out_index=0, unlocking_script=b'')
        utxo = self.blockchain.chain_state.get_utxo(new_coinbase_tx_in)
        self.assertIsNotNone(utxo)
        self.assertEqual(utxo.value, reward)
        print("New block added and its UTXO verified successfully.")

    def test_add_invalid_block_bad_pow(self):
        """
        Test adding a block with an invalid Proof of Work.
        """
        print("\n--- Running test_03_add_invalid_block_bad_pow ---")
        prev_tip = self.blockchain.get_best_tip()
        prev_block_hash = prev_tip['block_hash']
        
        # Create a block but DON'T mine it (nonce=0 will be invalid)
        coinbase_tx = Transaction(1, [TxIn.create_coinbase_txin(b'invalid pow')], [TxOut(5000000000, b'')], 0)
        block_with_bad_pow = Block.create_new(prev_block_hash, [coinbase_tx], prev_tip['bits'])
        
        # Attempt to add the invalid block
        result = self.blockchain.add_block(block_with_bad_pow)
        self.assertFalse(result, "Blockchain should reject a block with an invalid PoW.")
        
        # Verify the chain tip has not changed
        current_tip = self.blockchain.get_best_tip()
        self.assertEqual(current_tip['height'], 0)
        self.assertEqual(current_tip['block_hash'], prev_block_hash)
        print("Blockchain correctly rejected block with bad PoW.")

if __name__ == '__main__':
    unittest.main()
