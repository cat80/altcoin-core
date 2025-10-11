import unittest
from unittest.mock import Mock, patch
from core.block_validator import BlockValidator
from core.block import Block
from core.block_header import BlockHeader
from core.transaction import Transaction, TxIn, TxOut

class TestBlockValidator(unittest.TestCase):

    def setUp(self):
        """Setup common objects for tests."""
        self.mock_utxo_view = Mock()

        # Coinbase transaction
        self.coinbase_tx = Mock(spec=Transaction)
        self.coinbase_tx.is_coinbase.return_value = True
        self.coinbase_tx.tx_ins = [Mock(spec=TxIn)]
        self.coinbase_tx.tx_outs = [Mock(spec=TxOut, value=5000)]
        
        # Regular transaction spending a 1000-unit UTXO and creating a 900-unit output (100 fee)
        self.tx_in1 = Mock(spec=TxIn)
        self.tx_out1 = Mock(spec=TxOut, value=900)
        self.regular_tx1 = Mock(spec=Transaction)
        self.regular_tx1.is_coinbase.return_value = False
        self.regular_tx1.tx_ins = [self.tx_in1]
        self.regular_tx1.tx_outs = [self.tx_out1]
        self.regular_tx1.hash.return_value = b'\x1a' * 32

        # UTXO that will be "found" by the mock_utxo_view
        self.utxo1 = Mock(spec=TxOut, value=1000)

    def test_check_transactions_and_get_fees_valid(self):
        """Test a valid list of transactions, expecting correct fee calculation."""
        self.mock_utxo_view.get_utxo.return_value = self.utxo1
        transactions = [self.coinbase_tx, self.regular_tx1]
        
        with patch.object(BlockValidator, 'get_block_reward', return_value=5000):
            total_fees = BlockValidator.check_transactions_and_get_fees(transactions, self.mock_utxo_view, 1)
            self.assertEqual(total_fees, 100) # 1000 in - 900 out = 100 fee
        
        self.mock_utxo_view.get_utxo.assert_called_once_with(self.tx_in1)

    def test_fails_on_empty_transactions(self):
        """Test that it raises ValueError for an empty transaction list."""
        with self.assertRaisesRegex(ValueError, "Transaction list cannot be empty"):
            BlockValidator.check_transactions_and_get_fees([], self.mock_utxo_view, 1)

    def test_fails_on_no_coinbase(self):
        """Test that it raises ValueError if the first transaction is not a coinbase."""
        with self.assertRaisesRegex(ValueError, "First transaction must be a coinbase"):
            BlockValidator.check_transactions_and_get_fees([self.regular_tx1], self.mock_utxo_view, 1)

    def test_fails_on_multiple_coinbases(self):
        """Test that it raises ValueError for more than one coinbase transaction."""
        transactions = [self.coinbase_tx, self.coinbase_tx]
        with self.assertRaisesRegex(ValueError, "More than one coinbase transaction found"):
            BlockValidator.check_transactions_and_get_fees(transactions, self.mock_utxo_view, 1)

    def test_fails_on_utxo_not_found(self):
        """Test that it raises ValueError if an input UTXO is not found."""
        self.mock_utxo_view.get_utxo.return_value = None
        transactions = [self.coinbase_tx, self.regular_tx1]
        with self.assertRaisesRegex(ValueError, "Input UTXO not found"):
            BlockValidator.check_transactions_and_get_fees(transactions, self.mock_utxo_view, 1)

    def test_fails_on_insufficient_funds(self):
        """Test that it raises ValueError if input sum is less than output sum."""
        # Input is 1000, but let's make the output 1100
        self.regular_tx1.tx_outs = [Mock(spec=TxOut, value=1100)]
        self.mock_utxo_view.get_utxo.return_value = self.utxo1
        transactions = [self.coinbase_tx, self.regular_tx1]
        
        with self.assertRaisesRegex(ValueError, "Input sum less than output sum"):
            BlockValidator.check_transactions_and_get_fees(transactions, self.mock_utxo_view, 1)

    def test_fails_on_coinbase_overspend(self):
        """Test that it raises ValueError if coinbase output exceeds reward plus fees."""
        # Fees are 100. Reward is 5000. Total allowed is 5100.
        self.coinbase_tx.tx_outs = [Mock(spec=TxOut, value=5101)]
        self.mock_utxo_view.get_utxo.return_value = self.utxo1
        transactions = [self.coinbase_tx, self.regular_tx1]

        with patch.object(BlockValidator, 'get_block_reward', return_value=5000):
            with self.assertRaisesRegex(ValueError, "Coinbase output value exceeds block reward plus fees"):
                BlockValidator.check_transactions_and_get_fees(transactions, self.mock_utxo_view, 1)

    def test_check_block_integration(self):
        """Test the main check_block function integrates correctly."""
        mock_block = Mock(spec=Block)
        mock_block.transactions = [self.coinbase_tx]
        prev_header_info = {'height': 0}

        # Test success case
        with patch.object(BlockValidator, 'check_merkle_root', return_value=True):
            with patch.object(BlockValidator, 'check_transactions_and_get_fees') as mock_check_tx:
                result = BlockValidator.check_block(mock_block, self.mock_utxo_view, None, prev_header_info)
                self.assertTrue(result)
                mock_check_tx.assert_called_once_with(mock_block.transactions, self.mock_utxo_view, 1)

        # Test failure case from check_transactions_and_get_fees
        with patch.object(BlockValidator, 'check_merkle_root', return_value=True):
            with patch.object(BlockValidator, 'check_transactions_and_get_fees', side_effect=ValueError("Test error")) as mock_check_tx:
                result = BlockValidator.check_block(mock_block, self.mock_utxo_view, None, prev_header_info)
                self.assertFalse(result)
                mock_check_tx.assert_called_once_with(mock_block.transactions, self.mock_utxo_view, 1)

if __name__ == '__main__':
    unittest.main()
