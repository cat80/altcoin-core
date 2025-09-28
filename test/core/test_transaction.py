import unittest
import io
import hashlib

# 假设你的项目结构正确，可以从src导入
# 注意：你需要将你上传的 transaction.py 文件中的 `from crypto import ...`
# 修改为 `from src.utils.crypto import ...` 以匹配我们的项目结构。
from core.transaction import TxIn, TxOut, Transaction
from utils.crypto import generate_keypair, sign_data, verify_signature, ecdsa, CURVE, get_address_by_public_key, hash_data


class TestTransaction(unittest.TestCase):
    """
    针对 Transaction 及其组件的单元测试套件。
    """

    def setUp(self):
        """
        在每个测试方法执行前运行，用于设置共享的测试数据。
        """
        # 创建两个钱包（密钥对）
        self.wallet1_private, self.wallet1_public = generate_keypair()
        self.wallet2_private, self.wallet2_public = generate_keypair()

        # 根据公钥生成20字节的地址哈希，作为锁定脚本
        self.locking_script1 = get_address_by_public_key(self.wallet1_public).encode('utf8')
        self.locking_script2 = get_address_by_public_key(self.wallet2_public).encode('utf8')

    def test_txout_serialization_roundtrip(self):
        """测试 TxOut 的序列化 -> 反序列化往返过程。"""
        original_tx_out = TxOut(value=50000, locking_script=self.locking_script1)
        serialized = original_tx_out.serialize()
        # 使用 io.BytesIO 来模拟文件/网络流
        stream = io.BytesIO(serialized)
        deserialized = TxOut.deserialize(stream)

        self.assertEqual(original_tx_out, deserialized, "TxOut的序列化往返测试失败")

    def test_txin_serialization_roundtrip(self):
        """测试 TxIn 的序列化 -> 反序列化往返过程。"""
        original_tx_in = TxIn(
            prev_tx_hash=hash_data(b'genesis'),
            prev_tx_out_index=1,
            unlocking_script=b'\xaa' * 129  # 模拟 64字节签名 + 65字节公钥
        )
        serialized = original_tx_in.serialize()
        stream = io.BytesIO(serialized)
        deserialized = TxIn.deserialize(stream)

        self.assertEqual(original_tx_in, deserialized, "TxIn的序列化往返测试失败")

    def test_transaction_full_serialization_roundtrip(self):
        """测试包含多个输入输出的完整交易的往返过程。"""
        original_tx = Transaction(
            version=1,
            tx_ins=[
                TxIn(prev_tx_hash=b'\x11' * 32, prev_tx_out_index=0, unlocking_script=b'\xaa' * 129),
                TxIn(prev_tx_hash=b'\x22' * 32, prev_tx_out_index=1, unlocking_script=b'\xbb' * 129)
            ],
            tx_outs=[
                TxOut(value=100, locking_script=self.locking_script1),
                TxOut(value=200, locking_script=self.locking_script2)
            ],
            locktime=0,
            op_return_data=b'AltCoin test data'
        )

        serialized = original_tx.serialize()
        steam =  io.BytesIO(serialized)
        deserialized = Transaction.deserialize(steam)

        self.assertEqual(original_tx, deserialized, "完整Transaction的序列化往返测试失败")

    def test_signature_verification_flow(self):
        """
        测试一个真实的交易签名和验证流程。
        这个测试用例是整个系统的核心。
        """
        # 1. 构造一个前置交易(tx0)，它创建了一个归属于 wallet1 的UTXO
        tx0_out = TxOut(value=50000, locking_script=self.locking_script1)
        tx0 = Transaction(version=1, tx_ins=[], tx_outs=[tx0_out], locktime=0)
        tx0_hash = tx0.hash()  # 计算 tx0 的哈希作为 TxID

        # 模拟一个UTXO池，其中包含了我们刚刚创建的UTXO
        utxo_map = {(tx0_hash, 0): tx0_out}

        # 2. 构造一个新交易(tx1)来花费这个UTXO
        # a. 先创建一个不带解锁脚本的输入，指向 tx0 的输出
        tx1_in_unsigned = TxIn(prev_tx_hash=tx0_hash, prev_tx_out_index=0, unlocking_script=b'')

        # b. 创建一个不带签名的交易模板，用于生成待签名数据
        tx1_template = Transaction(
            version=1,
            tx_ins=[tx1_in_unsigned],
            tx_outs=[TxOut(value=49000, locking_script=self.locking_script2)],  # 转账给wallet2，留下1000手续费
            locktime=0
        )

        # c. 生成用于签名的哈希 (这是最关键的一步)
        hash_for_signing = tx1_template.serialize(for_signing=True)

        # d. 使用 wallet1 的私钥对这个哈希进行签名
        signature = sign_data( hash_for_signing,self.wallet1_private,)
        public_key_bytes = self.wallet1_public.to_string()

        # e. 构建最终的解锁脚本
        unlocking_script = signature + public_key_bytes

        # 3. 构建最终的、包含有效签名的完整交易
        final_tx1 = Transaction(
            version=1,
            tx_ins=[TxIn(tx1_in_unsigned.prev_tx_hash, tx1_in_unsigned.prev_tx_out_index, unlocking_script)],
            tx_outs=tx1_template.tx_outs,
            locktime=0
        )

        # 4. 验证这笔交易的签名
        self.assertTrue(final_tx1.verify_signature(), "有效签名应该验证通过")

        # 5. 测试一个无效签名场景（用错误的密钥签名）
        wrong_signature = sign_data(hash_for_signing,self.wallet2_private)  # 使用wallet2的私钥
        wrong_unlocking_script = wrong_signature + self.wallet1_public.to_string()
        bad_tx1 = Transaction(
            version=1,
            tx_ins=[TxIn(tx1_in_unsigned.prev_tx_hash, tx1_in_unsigned.prev_tx_out_index, wrong_unlocking_script)],
            tx_outs=tx1_template.tx_outs,
            locktime=0
        )
        self.assertFalse(bad_tx1.verify_signature(), "使用错误密钥的签名应该验证失败")


if __name__ == '__main__':
    unittest.main()