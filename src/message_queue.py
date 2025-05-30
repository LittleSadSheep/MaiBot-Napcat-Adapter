import asyncio
import time
from typing import Dict, Any
from .config import global_config
from .logger import logger

response_dict: Dict[str, Dict[str, Any]] = {}
response_time_dict: Dict = {}
message_queue = asyncio.Queue()


async def get_response(message_id: str, timeout: float = 30) -> Dict[str, Any]:
    """获取响应，如果超时则返回None"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if message_id in response_dict:
            return response_dict.pop(message_id)["response"]
        await asyncio.sleep(0.1)
    return None


async def put_response(message_id: str, response: Dict[str, Any]):
    """将响应放入字典中"""
    response_dict[message_id] = {
        "response": response,
        "time": time.time()
    }


async def check_timeout_response():
    """检查并删除超时的响应"""
    while True:
        current_time = time.time()
        timeout_keys = [
            key for key, value in response_dict.items()
            if current_time - value["time"] > 30
        ]
        for key in timeout_keys:
            response_dict.pop(key)
        if timeout_keys:
            logger.info(f"已删除 {len(timeout_keys)} 条超时响应消息")
        await asyncio.sleep(30)  # 使用固定的30秒间隔
