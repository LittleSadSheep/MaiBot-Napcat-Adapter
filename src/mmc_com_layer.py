import asyncio
import json
import websockets
from maim_message import Router, RouteConfig, TargetConfig
from .config import global_config
from .logger import logger
from .send_handler import send_handler
from .message_queue import message_queue

route_config = RouteConfig(
    route_config={
        global_config.platform: TargetConfig(
            url=f"ws://{global_config.maibot_host}:{global_config.maibot_port}/ws",
            token=None,
        )
    }
)
router = Router(route_config)


async def mmc_start_com():
    global router
    retry_count = 0
    max_retries = 5
    retry_delay = 5

    while True:
        try:
            uri = f"ws://{global_config.maibot_host}:{global_config.maibot_port}/ws"
            logger.info(f"正在尝试连接到MaiBot服务器: {uri}")
            
            async with websockets.connect(
                uri=uri,
                ping_interval=None,
                close_timeout=5,
            ) as websocket:
                router = websocket
                retry_count = 0  # 重置重试计数
                logger.info("已成功连接到MaiBot服务器")
                
                while True:
                    try:
                        message = await websocket.recv()
                        await message_queue.put(json.loads(message))
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.warning(f"与MaiBot服务器的连接已断开: {e}")
                        break
                    except json.JSONDecodeError as e:
                        logger.error(f"解析消息时出错: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"处理消息时出错: {e}")
                        continue

        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"连接MaiBot服务器时收到无效状态码: {e}")
        except websockets.exceptions.InvalidMessage as e:
            logger.error(f"连接MaiBot服务器时收到无效消息: {e}")
        except ConnectionRefusedError:
            logger.error(f"连接被拒绝，请确保MaiBot服务器正在运行且地址正确: {global_config.maibot_host}:{global_config.maibot_port}")
        except Exception as e:
            logger.error(f"连接MaiBot服务器时出错: {e}")

        retry_count += 1
        if retry_count >= max_retries:
            logger.error(f"已达到最大重试次数({max_retries})，请检查MaiBot服务器状态和配置")
            retry_count = 0  # 重置重试计数，继续尝试
            retry_delay = 30  # 增加重试延迟
        else:
            retry_delay = min(retry_delay * 2, 30)  # 指数退避，最大30秒

        logger.info(f"将在{retry_delay}秒后重试连接...")
        await asyncio.sleep(retry_delay)


async def mmc_stop_com():
    if router:
        try:
            await router.close()
            logger.info("已关闭与MaiBot服务器的连接")
        except Exception as e:
            logger.error(f"关闭连接时出错: {e}")
