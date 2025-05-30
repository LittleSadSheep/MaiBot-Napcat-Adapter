from .logger import logger
from .config import global_config
from .qq_emoji_list import qq_face
import time
import asyncio
import json
import discord
from typing import List, Tuple, Optional
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

    async def handle_meta_event(self, message: dict) -> None:
        """处理Discord元事件"""
        event_type = message.get("type")
        if event_type == "ready":
            self_id = message.get("user", {}).get("id")
            self.last_heart_beat = time.time()
            logger.info(f"Bot {self_id} 连接成功")
            asyncio.create_task(self.check_heartbeat(self_id))
        elif event_type == "heartbeat":
            self.last_heart_beat = time.time()
            self.interval = message.get("interval", 30)
        else:
            logger.warning(f"未知的元事件类型: {event_type}")

    async def check_heartbeat(self, id: str) -> None:
        while True:
            now_time = time.time()
            if now_time - self.last_heart_beat > self.interval + 3:
                logger.warning(f"Bot {id} 连接已断开")
                break
            else:
                logger.debug("心跳正常")
            await asyncio.sleep(self.interval)

    def check_allow_to_chat(self, user_id: str, channel_id: Optional[str]) -> bool:
        """
        检查是否允许聊天
        Parameters:
            user_id: str: 用户ID
            channel_id: str: 频道ID
        Returns:
            bool: 是否允许聊天
        """
        if channel_id:
            if global_config.channel_list_type == "whitelist" and channel_id not in global_config.channel_list:
                logger.warning("频道不在聊天白名单中，消息被丢弃")
                return False
            elif global_config.channel_list_type == "blacklist" and channel_id in global_config.channel_list:
                logger.warning("频道在聊天黑名单中，消息被丢弃")
                return False
        else:
            if global_config.private_list_type == "whitelist" and user_id not in global_config.private_list:
                logger.warning("用户不在聊天白名单中，消息被丢弃")
                return False
            elif global_config.private_list_type == "blacklist" and user_id in global_config.private_list:
                logger.warning("用户在聊天黑名单中，消息被丢弃")
                return False
        if user_id in global_config.ban_user_id:
            logger.warning("用户在全局黑名单中，消息被丢弃")
            return False
        return True

    async def handle_raw_message(self, raw_message: dict) -> None:
        """
        处理Discord原始消息
        Parameters:
            raw_message: dict: 原始消息
        """
        message_type = "private" if isinstance(raw_message.get("channel"), discord.DMChannel) else "group"
        message_id = str(raw_message.get("id"))
        message_time = time.time()

        template_info = None
        format_info = FormatInfo(
            content_format=["text", "image", "emoji"],
            accept_format=["text", "image", "emoji", "reply"],
        )

        if message_type == "private":
            sender_info = raw_message.get("author")
            if not self.check_allow_to_chat(str(sender_info.id), None):
                return None

            user_info = UserInfo(
                platform=global_config.platform_name,
                user_id=str(sender_info.id),
                user_nickname=sender_info.name,
                user_cardname=sender_info.display_name,
            )
            group_info = None

        else:  # group message
            sender_info = raw_message.get("author")
            channel_info = raw_message.get("channel")
            
            if not self.check_allow_to_chat(str(sender_info.id), str(channel_info.id)):
                return None

            user_info = UserInfo(
                platform=global_config.platform_name,
                user_id=str(sender_info.id),
                user_nickname=sender_info.name,
                user_cardname=sender_info.display_name,
            )

            group_info = GroupInfo(
                platform=global_config.platform_name,
                group_id=str(channel_info.id),
                group_name=channel_info.name,
            )

        # 处理消息内容
        message_segments = await self.handle_real_message(raw_message)
        if not message_segments:
            return None

        # 构造消息元数据
        message_info = BaseMessageInfo(
            message_id=message_id,
            message_time=message_time,
            user_info=user_info,
            group_info=group_info,
            template_info=template_info,
            format_info=format_info,
        )

        # 构造消息体
        message = MessageBase(
            message_info=message_info,
            message_segment=message_segments,
            raw_message=raw_message,
        )

        # 发送消息到MaiBot
        await self.maibot_router.send_message(message)

    async def handle_real_message(self, raw_message: dict, in_reply: bool = False) -> List[Seg]:
        """处理实际消息内容"""
        segments = []
        
        # 处理引用消息
        if raw_message.reference and raw_message.reference.resolved:
            segments.append(Seg(
                type="reply",
                data={"id": str(raw_message.reference.message_id)}
            ))

        # 处理文本内容
        if raw_message.content:
            segments.append(Seg(
                type="text",
                data={"text": raw_message.content}
            ))

        # 处理表情
        for emoji in raw_message.emojis:
            segments.append(Seg(
                type="emoji",
                data={"emoji": str(emoji)}
            ))

        # 处理图片附件
        for attachment in raw_message.attachments:
            if attachment.content_type and attachment.content_type.startswith('image/'):
                segments.append(Seg(
                    type="image",
                    data={"file": attachment.url}
                ))

        return segments

    async def handle_notice(self, raw_message: dict) -> None:
        """处理Discord通知事件"""
        notice_type = raw_message.get("type")
        
        if notice_type == "typing_start":
            # 处理正在输入通知
            pass
        elif notice_type == "message_reaction_add":
            # 处理消息反应通知
            pass
        elif notice_type == "message_reaction_remove":
            # 处理消息反应移除通知
            pass
        else:
            logger.warning(f"未知的通知类型: {notice_type}")

    async def message_process(self, message_base: MessageBase) -> None:
        """处理从MaiBot返回的消息"""
        # 实现消息处理逻辑
        pass


recv_handler = RecvHandler()
