from storage.rocksdb_wrapper import RocksDBWrapper
import random

def get_keys():
      utxos = [
        {
            "tx_hash": "132194fbfa50424777f73492713e84533e2bf612bbe07655da7064e7a3a9f229",
            "output_index": 1,
            "value": 143715401
        },
        {
            "tx_hash": "69f21d009c1c032eb2005062a12471d76716206aac2ec3ab2c6c90001e00b8d9",
            "output_index": 0,
            "value": 149909599
        },
        {
            "tx_hash": "306400ca533533e4dcc9b5d10c46e12afaf250496cc647a024e3e92843ec3755",
            "output_index": 1,
            "value": 16666299
        },
        {
            "tx_hash": "7ee5bdfa8028363c6572065b33bed67c0acad0b0e25b3ad6624d6e3775921666",
            "output_index": 1,
            "value": 14799501
        },
        {
            "tx_hash": "3f4dce3bec422a7dc3d26f621842aeff2d9d7dca95fa3183c63a6b64cdc4c41e",
            "output_index": 0,
            "value": 12584699
        },
        {
            "tx_hash": "09e9c78f922334147df448d2384c18e9b53f0352667b8ac27baf76dcbdc4f235",
            "output_index": 1,
            "value": 475789802
        },
        {
            "tx_hash": "c643d964fb1839a10ad5d2d46644e3e0dcc8dde3eea37d2c56d77833d33c534a",
            "output_index": 1,
            "value": 469417403
        },
        {
            "tx_hash": "43941c36e14002a32e4eb71972937ae8eee83d39b20d1a40536b06c89ff3eff3",
            "output_index": 1,
            "value": 19921700
        },
        {
            "tx_hash": "eb4fd9ff7415dd9422050af276917f451fb00ae4f2f8614caebfab07bf13554f",
            "output_index": 1,
            "value": 312292300
        },
        {
            "tx_hash": "334f45a5362f9d5d6137b019d2ee476cc33b5003884dbb03ae98577ff0a21ac3",
            "output_index": 0,
            "value": 383770100
        },
        {
            "tx_hash": "d4aca3483012403bf7ff9f1e7ce94818451302578768e84b86dd63c349e18979",
            "output_index": 0,
            "value": 142217600
        },
        {
            "tx_hash": "1525ad8057ab2bfd5e62e995873a9ff36881ea0d176f95c7262243917eb6316a",
            "output_index": 0,
            "value": 122084499
        },
        {
            "tx_hash": "3d76751f0229fdd7b0f03badff71a6a7ba3cc9480269af7365e76301bec2bf36",
            "output_index": 0,
            "value": 394999099
        },
        {
            "tx_hash": "92047bca3e48b18d55616d0f25137e0f3ab506b83c0bdf65c5249cc80204cf8c",
            "output_index": 0,
            "value": 8694100
        },
        {
            "tx_hash": "11ae9d44c7e8bddb834c259598d4ef5267b6eb4f1f805dad7a56ea283ca679bb",
            "output_index": 0,
            "value": 127244700
        },
        {
            "tx_hash": "89cb9cba9d1c301496f1c497fa0587141dd40dfe586a58eb814800d9c6eccd2b",
            "output_index": 0,
            "value": 9277199
        },
        {
            "tx_hash": "f0d7b4686ec1889990cb0c7a00c5479c1f25a4604411a3619468ce0e41f62fd7",
            "output_index": 0,
            "value": 8744100
        },
        {
            "tx_hash": "9e4eabe628513d248f0fd66f74ad4204c4534b87daefefed47f072cb043da041",
            "output_index": 0,
            "value": 79332199
        },
        {
            "tx_hash": "e712ffe7f8b1944f5392053e6b55bb3096352c88ca1b7fc240e6ccd41fc7c80e",
            "output_index": 0,
            "value": 140160599
        },
        {
            "tx_hash": "8f94e2ea93401e95fedcf9fdb413611a2d433ef57c63f783975a6c27525ed8c8",
            "output_index": 0,
            "value": 209149299
        },
        {
            "tx_hash": "5d4e4c4ec2be6480290c5220ac9c850c0080b650667d2af7abd97b3e59c77629",
            "output_index": 0,
            "value": 341951299
        },
        {
            "tx_hash": "857db6f1d6cd84060cf4ef8b563c722abffde2813eb2d2a7510b1c0457f6933f",
            "output_index": 0,
            "value": 97219699
        },
        {
            "tx_hash": "71e0d96c6a4f797f37800e686314c3e2159a83239d0e6bc767ed2b38b1168801",
            "output_index": 0,
            "value": 123702200
        },
        {
            "tx_hash": "56a53e61de28f5f37ae9ed2c0138acb0f757d7d513c0690a167543a99fd327e4",
            "output_index": 0,
            "value": 368983799
        } ]
      keys = []
      for item in utxos:
          keys.append([bytes.fromhex(  item['tx_hash']) + item['output_index'].to_bytes(4,'little'),item])
      return keys

def get_all_keys_simple(db):
    """
    简单尝试获取所有键的方法
    """
    keys = []
    try:
        # 尝试使用迭代器
        for key in db.iter_keys():
            keys.append(key)
    except Exception as e:
        print(f"迭代方法失败: {e}")
        # 如果迭代方法失败，尝试其他方式
        print("无法通过迭代获取键")
    return keys

def get_sample_keys(rocksdb, sample_size=10):
    """
    从RocksDB中随机获取指定数量的键作为样本
    
    Args:
        rocksdb: RocksDBWrapper实例
        sample_size: 样本大小，默认为10
    
    Returns:
        list: 键的列表
    """
    try:
        all_keys = []
        for key in rocksdb.iter_keys():
            all_keys.append(key)
        if len(all_keys) <= sample_size:
            return all_keys
        return random.sample(all_keys, sample_size)
    except NotImplementedError as e:
        print(f"错误: {e}")
        return []
    except Exception as e:
        print(f"获取样本键时出错: {e}")
        return []

def set_key(rocksdb,key,value):
    rocksdb.put(key,value)
    
def get_key(rocksdb,key):
    return rocksdb.get(key)

if __name__ == "__main__":
    base_dir = r'/mnt/d/prj/web3/altcoin-core/nodes-data/node17880/'
    rocks = RocksDBWrapper(base_dir + "utxo-bak" )

    print(get_key(rocks,b'1122'))

    # tx_input.prev_tx_hash + tx_input.prev_tx_out_index.to_bytes(4, 'little')
    index = 0
    all_keys = get_keys()
    print(get_keys())
    key = bytes.fromhex(  '7b228829d4da359d9a2b00c783c77af47f8139c80c0a2690954f24fbd703eaba') + index.to_bytes(4,'little')
    for item in all_keys:
        print(rocks.get(item[0]),item)
    print(rocks.get(key))
    
    # 获取样本键
    # sample_keys = get_sample_keys(rocks, 5)
    # print(f"\n获取了 {len(sample_keys)} 个样本键:")
    # for key in sample_keys:
    #     print(f"  {key}")
    # print(rocks.get(b'C\xc3a\x14\x00\x00\x00\x00"\x00\x00\x001G8NoV8p6ZSwyJ2jUfcNeFcPoJUDctwgzb'))