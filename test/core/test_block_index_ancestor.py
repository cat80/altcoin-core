import unittest
import os
from src.core.block_header import BlockHeader
from src.core.block_index import BlockIndex
from src.storage.sql_alchemy_wrapper import SQLAlchemyWrapper

# Helper function to create a chain of headers
def create_header_chain(base_header, length):
    chain = []
    prev_header = base_header
    for i in range(length):
        new_header = BlockHeader(
            version=1,
            prev_block_hash=prev_header.hash(),
            merkle_root=os.urandom(32),
            timestamp=prev_header.timestamp + 600 + i,
            bits=prev_header.bits,
            nonce=i
        )
        chain.append(new_header)
        prev_header = new_header
    return chain

class TestFindCommonAncestor(unittest.TestCase):
    def setUp(self):
        self.output_dir = "test-output"
        os.makedirs(self.output_dir, exist_ok=True)
        self.db_path = os.path.join(self.output_dir, "test_ancestor_db.sqlite")
        
        # Ensure the database file does not exist from a previous run
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        self.sqldb = SQLAlchemyWrapper(self.db_path)
        self.sqldb.create_all_tables()
        self.block_index = BlockIndex(self.sqldb)
        
        # Create a genesis block
        self.genesis_header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=os.urandom(32),
            timestamp=1609459200,
            bits=0x207fffff,
            nonce=0
        )
        self.block_index.add_header(self.genesis_header, height=0, total_work=1, file_index=0, file_offset=0)

    def tearDown(self):
        # The database file is now in the test-output directory, 
        # we can leave it there for inspection or remove it.
        # For cleanliness, we'll remove it.
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def add_chain_to_index(self, base_header, base_height, chain):
        prev_header_info = {'total_work': 1, 'height': base_height}
        for header in chain:
            height = prev_header_info['height'] + 1
            total_work = prev_header_info['total_work'] + 1 # Simplified total_work for testing
            self.block_index.add_header(header, height=height, total_work=total_work, file_index=0, file_offset=0)
            prev_header_info = {'height': height, 'total_work': total_work}

    def test_simple_fork(self):
        # G -> A -> B -> C (old_tip)
        #      \
        #       -> D -> E (new_tip)
        
        chain_a = create_header_chain(self.genesis_header, 1) # Block A
        self.add_chain_to_index(self.genesis_header, 0, chain_a)
        
        block_a = chain_a[0]
        chain_bc = create_header_chain(block_a, 2) # Blocks B, C
        self.add_chain_to_index(block_a, 1, chain_bc)
        
        chain_de = create_header_chain(block_a, 2) # Blocks D, E
        self.add_chain_to_index(block_a, 1, chain_de)
        
        old_tip_hash = chain_bc[-1].hash()
        new_tip_hash = chain_de[-1].hash()
        
        ancestor, rollback, apply = self.block_index.find_common_ancestor(new_tip_hash, old_tip_hash)
        
        self.assertEqual(ancestor, block_a.hash())
        self.assertEqual(len(rollback), 2)
        self.assertEqual([b['block_hash'] for b in rollback], [h.hash() for h in reversed(chain_bc)])
        self.assertEqual(len(apply), 2)
        self.assertEqual([b['block_hash'] for b in apply], [h.hash() for h in chain_de])

    def test_new_chain_is_longer_extension(self):
        # G -> A -> B (old_tip) -> C -> D (new_tip)
        chain_ab = create_header_chain(self.genesis_header, 2)
        self.add_chain_to_index(self.genesis_header, 0, chain_ab)
        
        block_b = chain_ab[1]
        chain_cd = create_header_chain(block_b, 2)
        self.add_chain_to_index(block_b, 2, chain_cd)
        
        old_tip_hash = block_b.hash()
        new_tip_hash = chain_cd[-1].hash()
        
        ancestor, rollback, apply = self.block_index.find_common_ancestor(new_tip_hash, old_tip_hash)
        
        self.assertEqual(ancestor, old_tip_hash)
        self.assertEqual(len(rollback), 0)
        self.assertEqual(len(apply), 2)
        self.assertEqual([b['block_hash'] for b in apply], [h.hash() for h in chain_cd])

    def test_old_chain_is_longer_fork(self):
        # G -> A -> B (new_tip)
        #      \
        #       -> C -> D (old_tip)
        chain_ab = create_header_chain(self.genesis_header, 2)
        self.add_chain_to_index(self.genesis_header, 0, chain_ab)
        
        chain_cd = create_header_chain(self.genesis_header, 2)
        self.add_chain_to_index(self.genesis_header, 0, chain_cd)
        
        new_tip_hash = chain_ab[-1].hash()
        old_tip_hash = chain_cd[-1].hash()
        
        ancestor, rollback, apply = self.block_index.find_common_ancestor(new_tip_hash, old_tip_hash)
        
        self.assertEqual(ancestor, self.genesis_header.hash())
        self.assertEqual(len(rollback), 2)
        self.assertEqual([b['block_hash'] for b in rollback], [h.hash() for h in reversed(chain_cd)])
        self.assertEqual(len(apply), 2)
        self.assertEqual([b['block_hash'] for b in apply], [h.hash() for h in chain_ab])

    def test_tips_are_the_same(self):
        # G -> A -> B (old_tip, new_tip)
        chain_ab = create_header_chain(self.genesis_header, 2)
        self.add_chain_to_index(self.genesis_header, 0, chain_ab)
        
        tip_hash = chain_ab[-1].hash()
        
        ancestor, rollback, apply = self.block_index.find_common_ancestor(tip_hash, tip_hash)
        
        self.assertEqual(ancestor, tip_hash)
        self.assertEqual(len(rollback), 0)
        self.assertEqual(len(apply), 0)

    def test_fork_from_genesis(self):
        # G -> A (old_tip)
        #  \
        #   -> B (new_tip)
        chain_a = create_header_chain(self.genesis_header, 1)
        self.add_chain_to_index(self.genesis_header, 0, chain_a)
        
        chain_b = create_header_chain(self.genesis_header, 1)
        self.add_chain_to_index(self.genesis_header, 0, chain_b)
        
        old_tip_hash = chain_a[0].hash()
        new_tip_hash = chain_b[0].hash()
        
        ancestor, rollback, apply = self.block_index.find_common_ancestor(new_tip_hash, old_tip_hash)
        
        self.assertEqual(ancestor, self.genesis_header.hash())
        self.assertEqual(len(rollback), 1)
        self.assertEqual(rollback[0]['block_hash'], old_tip_hash)
        self.assertEqual(len(apply), 1)
        self.assertEqual(apply[0]['block_hash'], new_tip_hash)

    def test_invalid_tip(self):
        # Provide a hash that doesn't exist in the index
        chain_a = create_header_chain(self.genesis_header, 1)
        self.add_chain_to_index(self.genesis_header, 0, chain_a)
        
        valid_tip_hash = chain_a[0].hash()
        invalid_tip_hash = os.urandom(32)
        
        ancestor, rollback, apply = self.block_index.find_common_ancestor(valid_tip_hash, invalid_tip_hash)
        self.assertIsNone(ancestor)
        self.assertEqual(len(rollback), 0)
        self.assertEqual(len(apply), 0)
        
        ancestor, rollback, apply = self.block_index.find_common_ancestor(invalid_tip_hash, valid_tip_hash)
        self.assertIsNone(ancestor)
        self.assertEqual(len(rollback), 0)
        self.assertEqual(len(apply), 0)

if __name__ == '__main__':
    unittest.main()
