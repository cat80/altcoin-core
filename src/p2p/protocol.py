import logging
import struct
import json
import time
from typing import Any,Optional
from copy import deepcopy
NETWORK_MAGIC_HEADER = b'\xab\xcd\xef\x88'
# 定义进制的头 MAGIC +PAYLOADLEN+CHECKSUM+PAYLOAD
# 头部有14个 len(MAGI4C_HEADER)  + 4 + 4
HEADER_FORMAT = '<4s4sI'
HEADER_LEN = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD_LEN = 1024*1024*10
log = logging.getLogger(__name__)

class Message:
    type:str
    client_id:str
    timestamp:int
    request_id:Optional[str]
    response_to:Optional[str]
    payload:dict[str,Any]

    def __init__(self,msg_type,payload=None):
        self.client_id = ''
        self.payload= payload
        self.type = msg_type
        self.timestamp = int(time.time())
        self.response_to =None
        self.request_id= None
    @classmethod
    def from_dict(cls,dict_data:dict[str,Any]):
        """
            从字典中加载message
        :param dict_data:
        :return:
        """
        if not dict_data:
            return None
        msg = cls(dict_data.get('type'),dict_data.get('payload'))
        if dict_data.get('request_id'):
            msg.request_id = dict_data.get('request_id')
        if dict_data.get('response_to'):
            msg.response_to =  dict_data.get('response_to')
        return msg

    def to_response_msg(self,response_type,payload=None)->'Message':
        """
            转换成一个response对象，自动把request_id转换为response_to
        :param response_type:
        :param payload:
        :return:
        """
        response_msg = deepcopy(self)
        if self.request_id:
            response_msg.request_id = None
            response_msg.response_to = self.request_id
        response_msg.timestamp = int(time.time())
        response_msg.type = response_type
        response_msg.payload= payload or {}
        return response_msg

    def to_dict(self):
        """
            转换为传输的dict
        :return:
        """
        data = {
            "type": self.type,
            'client_id':self.client_id,  # 客户端id
            'timestamp': self.timestamp,
            "payload": self.payload
        }
        if self.response_to:
            data['response_to'] = self.response_to
        if self.request_id:
            data['request_id'] = self.request_id
        return data

    def __repr__(self):
        return str(self.to_dict())
class protocol():

    @staticmethod
    def serialize(msg:Message):

        payload_bytes = json.dumps(msg.to_dict()).encode('utf8')
        message_header = struct.pack(HEADER_FORMAT, NETWORK_MAGIC_HEADER, b'\x00\x00\x00\x00', len(payload_bytes))
        return message_header + payload_bytes

    @staticmethod
    def serialize_message(msg_type,payload=None,request_id:str=None,response_to:str=None):
        # 序列化消息
        msg = Message(msg_type=msg_type,payload=payload)
        msg.request_id = request_id
        msg.response_to = response_to
        return protocol.serialize(msg)

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

        if payload_len > MAX_PAYLOAD_LEN:
            log.warning(f'payload长度超过最大长度，重新开始读取数据')
            return await protocol.deserialize_stream(io_stream,b'') #start over read data
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
