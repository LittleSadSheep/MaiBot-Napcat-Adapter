from .logger import logger
from .config import global_config
import time
import asyncio
import json
import discord
from typing import List, Tuple, Optional, Dict, Any
import uuid

from . import MetaEventType, RealMessageType, MessageType, NoticeType
from maim_message import (
    UserInfo,
    GroupInfo,
    Seg,
    BaseMessageInfo,
    MessageBase,
    TemplateInfo,
    FormatInfo,
    Router,
)

from .utils import (
    get_group_info,
    get_member_info,
    get_image_base64,
    get_self_info,
    get_stranger_info,
    get_message_detail,
)
from .message_queue import get_response


class RecvHandler:
    maibot_router: Router = None
    bot: discord.Client = None

    def __init__(self):
        self.last_heart_beat = time.time()
        self.interval = global_config.heartbeat

    async def handle_meta_event(self, message: Dict[str, Any]) -> None:
        """处理元事件"""
        meta_event_type = message.get("meta_event_type")
        if meta_event_type == "heartbeat":
            # Discord不需要处理心跳
            pass
        elif meta_event_type == "lifecycle":
            # Discord不需要处理生命周期事件
            sub_type = message.get("sub_type")
            if sub_type == MetaEventType.Lifecycle.connect:
                self_id = message.get("self_id")
                self.last_heart_beat = time.time()
                logger.info(f"Bot {self_id} 连接成功")
                asyncio.create_task(self.check_heartbeat(self_id))

    async def check_heartbeat(self, id: int) -> None:
        while True:
            now_time = time.time()
            if now_time - self.last_heart_beat > self.interval + 3:
                logger.warning(f"Bot {id} 连接已断开")
                break
            else:
                logger.debug("心跳正常")
            await asyncio.sleep(self.interval)

    def check_allow_to_chat(self, user_id: int, channel_id: Optional[int]) -> bool:
        """
        检查是否允许聊天
        Parameters:
            user_id: int: 用户ID
            channel_id: int: 频道ID
        Returns:
            bool: 是否允许聊天
        """
        logger.debug(f"频道id: {channel_id}, 用户id: {user_id}")
        if channel_id:
            if global_config.channel_list_type == "whitelist" and channel_id not in global_config.channel_list:
                logger.warning("频道不在聊天白名单中，消息被丢弃")
                return False
            elif global_config.channel_list_type == "blacklist" and channel_id in global_config.channel_list:
                logger.warning("频道在聊天黑名单中，消息被丢弃")
                return False
        else:
            if global_config.private_list_type == "whitelist" and user_id not in global_config.private_list:
                logger.warning("私聊不在聊天白名单中，消息被丢弃")
                return False
            elif global_config.private_list_type == "blacklist" and user_id in global_config.private_list:
                logger.warning("私聊在聊天黑名单中，消息被丢弃")
                return False
        if user_id in global_config.ban_user_id:
            logger.warning("用户在全局黑名单中，消息被丢弃")
            return False
        return True

    async def handle_raw_message(self, message: Dict[str, Any]) -> None:
        """处理原始消息"""
        try:
            # 检查是否允许聊天
            user_id = message["sender"]["user_id"]
            channel_id = message.get("group_id") if message["message_type"] == "group" else None
            if not self.check_allow_to_chat(user_id, channel_id):
                return

            # 构造用户信息
            user_info = UserInfo(
                platform="discord",  # 使用固定的平台标识符
                user_id=str(message["sender"]["user_id"]),
                user_nickname=message["sender"].get("nickname", ""),
                user_cardname=message["sender"].get("card", "")
            )

            # 构造群组信息（如果是群消息）
            group_info = None
            if message["message_type"] == "group":
                group_info = GroupInfo(
                    platform="discord",  # 使用固定的平台标识符
                    group_id=str(message["group_id"]),
                    group_name=message.get("group_name", "")
                )

            # 构造消息信息
            message_info = BaseMessageInfo(
                platform="discord",  # 使用固定的平台标识符
                message_id=str(message["message_id"]),
                time=message["time"],
                user_info=user_info,
                group_info=group_info
            )

            # 构造消息段
            message_segments = []
            for segment in message["message"]:
                if segment["type"] == "text":
                    message_segments.append(Seg("text", segment["data"]["text"]))
                elif segment["type"] == "image":
                    message_segments.append(Seg("image", segment["data"]["file"]))
                elif segment["type"] == "reply":
                    message_segments.append(Seg("reply", segment["data"]["id"]))

            # 构造最终消息
            message_base = MessageBase(
                message_info=message_info,
                message_segment=Seg("seglist", message_segments)
            )

            # 发送消息到MaiBot
            if self.maibot_router:
                await self.maibot_router.send_message(message_base)
            else:
                logger.error("MaiBot路由器未初始化")

        except Exception as e:
            logger.error(f"处理消息时出错: {e}")

    async def handle_notice(self, message: Dict[str, Any]) -> None:
        """处理通知事件"""
        notice_type = message.get("notice_type")
        if notice_type == "group_increase":
            # 处理群成员增加事件
            pass
        elif notice_type == "group_decrease":
            # 处理群成员减少事件
            pass

    async def message_process(self, message: Dict[str, Any]) -> None:
        """处理消息"""
        post_type = message.get("post_type")
        if post_type == "message":
            await self.handle_raw_message(message)
        elif post_type == "meta_event":
            await self.handle_meta_event(message)
        elif post_type == "notice":
            await self.handle_notice(message)
        else:
            logger.warning(f"未知的post_type: {post_type}")


recv_handler = RecvHandler()
