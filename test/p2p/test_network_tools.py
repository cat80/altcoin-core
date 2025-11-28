import unittest
from src.p2p.network_tools import dict_bytes_to_hex, form_hex_dict


class TestNetworkTools(unittest.TestCase):
    
    def test_block_index_to_hex_with_none_input(self):
        """测试传入None时的情况"""
        result = dict_bytes_to_hex(None)
        self.assertIsNone(result)
        
    def test_block_index_to_hex_with_non_dict_input(self):
        """测试传入非字典类型时的情况"""
        result = dict_bytes_to_hex("not_a_dict")
        self.assertEqual(result, "not_a_dict")
        
    def test_block_index_to_hex_with_empty_dict(self):
        """测试传入空字典时的情况"""
        result = dict_bytes_to_hex({})
        self.assertEqual(result, {})
        
    def test_block_index_to_hex_with_bytes_values(self):
        """测试字典中含有bytes值的情况"""
        test_data = {
            'key1': b'\x00\x01\x02',
            'key2': 'normal_string',
            'key3': 123
        }
        expected = {
            'key1': '000102',
            'key2': 'normal_string',
            'key3': 123
        }
        result = dict_bytes_to_hex(test_data)
        self.assertEqual(result, expected)
        
    def test_block_index_to_hex_with_bytearray_values(self):
        """测试字典中含有bytearray值的情况"""
        test_data = {
            'key1': bytearray(b'\x00\x01\x02'),
            'key2': 'normal_string',
            'key3': 123
        }
        expected = {
            'key1': '000102',
            'key2': 'normal_string',
            'key3': 123
        }
        result = dict_bytes_to_hex(test_data)
        self.assertEqual(result, expected)
        
    def test_block_index_to_hex_with_nested_dict(self):
        """测试字典中含有嵌套字典的情况"""
        test_data = {
            'key1': b'\x00\x01\x02',
            'nested': {
                'inner_key': b'\x03\x04\x05',
                'inner_normal': 'inner_string'
            },
            'key2': 'normal_string'
        }
        expected = {
            'key1': '000102',
            'nested': {
                'inner_key': '030405',
                'inner_normal': 'inner_string'
            },
            'key2': 'normal_string'
        }
        result = dict_bytes_to_hex(test_data)
        self.assertEqual(result, expected)
        
    def test_block_index_to_hex_original_dict_unchanged(self):
        """测试原字典不会被修改"""
        original_bytes = b'\x00\x01\x02'
        test_data = {
            'key1': original_bytes
        }
        original_data = test_data.copy()
        dict_bytes_to_hex(test_data)
        self.assertEqual(test_data['key1'], original_bytes)  # 原数据未被修改
        
    def test_form_hex_block_index_with_none_input(self):
        """测试传入None时的情况"""
        result = form_hex_dict(None)
        self.assertIsNone(result)
        
    def test_form_hex_block_index_with_non_dict_input(self):
        """测试传入非字典类型时的情况"""
        result = form_hex_dict("not_a_dict")
        self.assertEqual(result, "not_a_dict")
        
    def test_form_hex_block_index_with_empty_dict(self):
        """测试传入空字典时的情况"""
        result = form_hex_dict({})
        self.assertEqual(result, {})
        
    def test_form_hex_block_index_with_hex_string_values(self):
        """测试字典中含有hex字符串值的情况"""
        test_data = {
            'key1': '000102',
            'key2': 'normal_string',
            'key3': 123
        }
        expected = {
            'key1': b'\x00\x01\x02',
            'key2': 'normal_string',
            'key3': 123
        }
        result = form_hex_dict(test_data)
        self.assertEqual(result, expected)
        
    def test_form_hex_block_index_with_invalid_hex_string(self):
        """测试字典中含有无效hex字符串的情况"""
        test_data = {
            'key1': 'invalid_hex',
            'key2': 'gg',  # 包含非法字符
            'key3': '123'   # 奇数长度
        }
        expected = {
            'key1': 'invalid_hex',
            'key2': 'gg',
            'key3': '123'
        }
        result = form_hex_dict(test_data)
        self.assertEqual(result, expected)
        
    def test_form_hex_block_index_with_nested_dict(self):
        """测试字典中含有嵌套字典的情况"""
        test_data = {
            'key1': '000102',
            'nested': {
                'inner_key': '030405',
                'inner_normal': 'inner_string'
            },
            'key2': 'normal_string'
        }
        expected = {
            'key1': b'\x00\x01\x02',
            'nested': {
                'inner_key': b'\x03\x04\x05',
                'inner_normal': 'inner_string'
            },
            'key2': 'normal_string'
        }
        result = form_hex_dict(test_data)
        self.assertEqual(result, expected)
        
    def test_form_hex_block_index_original_dict_unchanged(self):
        """测试原字典不会被修改"""
        original_hex = '000102'
        test_data = {
            'key1': original_hex
        }
        original_data = test_data.copy()
        form_hex_dict(test_data)
        self.assertEqual(test_data['key1'], original_hex)  # 原数据未被修改
        
    def test_round_trip_conversion(self):
        """测试往返转换：bytes -> hex -> bytes"""
        original_data = {
            'block_hash': b'\x00\x01\x02\x03\x04\x05',
            'prev_block_hash': b'\x06\x07\x08\x09\x0a\x0b',
            'merkle_root': b'\x0c\x0d\x0e\x0f\x10\x11',
            'normal_field': 'just_a_string',
            'numeric_field': 12345
        }
        
        # 转换为hex
        hex_data = dict_bytes_to_hex(original_data)
        
        # 再转换回bytes
        restored_data = form_hex_dict(hex_data)
        
        # 验证恢复的数据与原始数据相同
        self.assertEqual(restored_data, original_data)


if __name__ == '__main__':
    unittest.main()