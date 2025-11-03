import logging
import struct
import io
import json
import datetime
import time
from operator import index

NETWORK_MAGIC_HEADER = b'\xab\xcd\xef\x88'
# 定义进制的头 MAGIC +PAYLOADLEN+CHECKSUM+PAYLOAD
# 头部有14个 len(MAGI4C_HEADER)  + 4 + 4
HEADER_FORMAT = '<4s4sI'
HEADER_LEN = struct.calcsize(HEADER_FORMAT)

log = logging.getLogger(__name__)

class protocol():

    @staticmethod
    def serialize_message(msgtype,payload=None):
        data = {
            "type":msgtype,
            'client_id':"", #客户端id
            'timestamp':int(time.time()),
            "payload": payload or {}
        }
        payload_bytes = json.dumps(data).encode('utf8')
        message_header = struct.pack(HEADER_FORMAT, NETWORK_MAGIC_HEADER, b'\x00\x00\x00\x00', len(payload_bytes))
        return message_header+payload_bytes

    @staticmethod
    async def deserialize_stream(io_stream,buffer=b''):
        # 这里反序列化的核心逻辑。
        while True:
            idx = buffer.find(NETWORK_MAGIC_HEADER)
            if idx != -1:
                buffer = buffer[idx:]
            if len(buffer) > HEADER_LEN:
                break
            chuck = await io_stream.read(9024)
            # log.debug(f'buffer len:{len(buffer)}')
            if not chuck:
                return None,b''
            buffer += chuck
        _, check_sum, payload_len = struct.unpack(HEADER_FORMAT, buffer[:HEADER_LEN])
        buffer = buffer[HEADER_LEN:]
        while len(buffer) < payload_len:
            chuck = await io_stream.read(payload_len - len(buffer))
            if not chuck:
                log.debug("Exception details: Connection failed, no data received.", exc_info=True)
                raise Exception('连接失败未获取到数据') # 保持原有异常抛出，但增加日志
            buffer += chuck
        payload = (buffer[:payload_len]).decode('utf8')
        remaing_data = buffer[payload_len:]
        return json.loads(payload), remaing_data


    @staticmethod
    def create_ping():
        return protocol.serialize_message('ping')

    @staticmethod
    def create_pong():
        return protocol.serialize_message('pong')

    @staticmethod
    def create_payload(msgtype, payload=None):
        return protocol.serialize_message(msgtype,payload)
