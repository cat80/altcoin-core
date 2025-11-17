"""
    网络工具
"""

def dict_bytes_to_hex(block_index: dict):
    # bytes无法json序列化的问题
    if not block_index or not isinstance(block_index, dict):
        return block_index
    
    # 创建一个新的字典来存储结果
    result = {}
    
    # 遍历字典中的所有键值对
    for key, value in block_index.items():
        if isinstance(value, (bytes, bytearray)):
            # 如果值是bytes或bytearray类型，则转换为hex字符串
            result[key] = value.hex()
        elif isinstance(value, dict):
            # 如果值是嵌套字典，则递归处理
            result[key] = dict_bytes_to_hex(value)
        else:
            # 其他类型的值保持不变
            result[key] = value
            
    return result

def form_hex_dict(block_index: dict):
    # 这个函数的作用是将hex字符串转换回bytes
    if not block_index or not isinstance(block_index, dict):
        return block_index
    
    # 创建一个新的字典来存储结果
    result = {}
    
    # 遍历字典中的所有键值对
    for key, value in block_index.items():
        if isinstance(value, str) and len(value) % 2 == 0:
            # 尝试将看起来像hex的字符串转换回bytes
            try:
                # 检查是否可以被转换回bytes（简单的启发式检查）
                int(value, 16)
                result[key] = bytes.fromhex(value)
            except ValueError:
                # 如果转换失败，保留原始值
                result[key] = value
        elif isinstance(value, dict):
            # 如果值是嵌套字典，则递归处理
            result[key] = form_hex_dict(value)
        else:
            # 其他类型的值保持不变
            result[key] = value
            
    return result