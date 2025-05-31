from .logger import logger
from .config import global_config
from .qq_emoji_list import qq_face
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
    discord_bot: discord.Client = None

    def __init__(self):
        self.interval = global_config.discord_heartbeat_interval
        self.last_heart_beat = time.time()

    async def handle_meta_event(self, message: dict) -> None:
        event_type = message.get("meta_event_type")
        if event_type == MetaEventType.lifecycle:
            sub_type = message.get("sub_type")
            if sub_type == MetaEventType.Lifecycle.connect:
                self_id = message.get("self_id")
                self.last_heart_beat = time.time()
                logger.info(f"Bot {self_id} 连接成功")
                asyncio.create_task(self.check_heartbeat(self_id))
        elif event_type == MetaEventType.heartbeat:
            if message["status"].get("online") and message["status"].get("good"):
                self.last_heart_beat = time.time()
                self.interval = message.get("interval") / 1000
            else:
                self_id = message.get("self_id")
                logger.warning(f"Bot {self_id} Discord 端异常！")

    async def check_heartbeat(self, id: int) -> None:
        while True:
            now_time = time.time()
            if now_time - self.last_heart_beat > self.interval + 3:
                logger.warning(f"Bot {id} 连接已断开")
                break
            else:
                logger.debug("心跳正常")
            await asyncio.sleep(self.interval)

    def check_allow_to_chat(self, user_id: str, channel_id: Optional[str]) -> bool:
        # sourcery skip: hoist-statement-from-if, merge-else-if-into-elif
        """
        检查是否允许聊天
        Parameters:
            user_id: str: 用户ID
            channel_id: str: 频道ID
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

    async def handle_raw_message(self, raw_message: dict) -> None:
        # sourcery skip: low-code-quality, remove-unreachable-code
        """
        从Discord接受的原始消息处理

        Parameters:
            raw_message: dict: 原始消息
        """
        logger.debug(f"收到Discord原始消息: {json.dumps(raw_message, ensure_ascii=False, indent=2)}")
        
        message_type: str = raw_message.get("message_type")
        message_id: str = raw_message.get("message_id")
        message_time: float = time.time()

        template_info: TemplateInfo = None
        format_info: FormatInfo = FormatInfo(
            content_format=["text", "image", "emoji"],
            accept_format=["text", "image", "emoji", "reply", "voice", "command"],
        )

        if message_type == MessageType.private:
            sender_info: dict = raw_message.get("sender")

            if not self.check_allow_to_chat(sender_info.get("user_id"), None):
                return None

            # 发送者用户信息
            user_info: UserInfo = UserInfo(
                platform=global_config.platform,
                user_id=sender_info.get("user_id"),
                user_nickname=sender_info.get("nickname"),
                user_cardname=sender_info.get("card"),
            )

            # 不存在群信息
            group_info: GroupInfo = None

        elif message_type == MessageType.group:
            sender_info: dict = raw_message.get("sender")

            if not self.check_allow_to_chat(sender_info.get("user_id"), raw_message.get("group_id")):
                return None

            # 发送者用户信息
            user_info: UserInfo = UserInfo(
                platform=global_config.platform,
                user_id=sender_info.get("user_id"),
                user_nickname=sender_info.get("nickname"),
                user_cardname=sender_info.get("card"),
            )

            # 获取频道相关信息
            channel = self.discord_bot.get_channel(int(raw_message.get("group_id")))
            group_name = channel.name if channel else None

            group_info: GroupInfo = GroupInfo(
                platform=global_config.platform,
                group_id=raw_message.get("group_id"),
                group_name=group_name,
            )
        else:
            logger.warning(f"消息类型 {message_type} 不支持")
            return None

        # 处理消息内容
        message_segments = await self.handle_real_message(raw_message)
        if not message_segments:
            return None

        # 构造消息体
        message_base = MessageBase(
            message_info=BaseMessageInfo(
                platform=global_config.platform,
                message_id=message_id,
                time=message_time,
                user_info=user_info,
                group_info=group_info,
                template_info=template_info,
                format_info=format_info,
            ),
            message_segment=Seg(
                type="seglist",
                data=message_segments
            ),
        )

        logger.debug(f"发送给Maibot的消息: {json.dumps(message_base.to_dict(), ensure_ascii=False, indent=2)}")

        # 发送消息
        await self.message_process(message_base)

    async def handle_real_message(self, raw_message: dict, in_reply: bool = False) -> List[Seg] | None:
        # sourcery skip: low-code-quality
        """
        处理真实消息内容

        Parameters:
            raw_message: dict: 原始消息
            in_reply: bool: 是否在回复中

        Returns:
            List[Seg] | None: 消息段列表
        """
        message = raw_message.get("message", "")
        if not message:
            return None

        segments = []
        # 处理文本消息
        text_seg = await self.handle_text_message(raw_message)
        if text_seg:
            segments.append(text_seg)

        # 处理表情消息
        face_seg = await self.handle_face_message(raw_message)
        if face_seg:
            segments.append(face_seg)

        # 处理图片消息
        image_seg = await self.handle_image_message(raw_message)
        if image_seg:
            segments.append(image_seg)

        # 处理@消息
        if raw_message.get("message_type") == MessageType.group:
            at_seg = await self.handle_at_message(
                raw_message,
                self.discord_bot.user.id,
                raw_message.get("group_id"),
            )
            if at_seg:
                segments.append(at_seg)

        # 处理回复消息
        if not in_reply:
            reply_segs = await self.handle_reply_message(raw_message)
            if reply_segs:
                # 将回复消息段列表包装在一个Seg对象中
                segments.append(Seg(type="seglist", data=reply_segs))

        return segments

    async def handle_text_message(self, raw_message: dict) -> Seg:
        """
        处理文本消息

        Parameters:
            raw_message: dict: 原始消息

        Returns:
            Seg: 文本消息段
        """
        return Seg(type="text", data=raw_message.get("message", ""))

    async def handle_face_message(self, raw_message: dict) -> Seg | None:
        """
        处理表情消息

        Parameters:
            raw_message: dict: 原始消息

        Returns:
            Seg | None: 表情消息段
        """
        # Discord不支持表情，返回None
        return None

    async def handle_image_message(self, raw_message: dict) -> Seg | None:
        """
        处理图片消息

        Parameters:
            raw_message: dict: 原始消息

        Returns:
            Seg | None: 图片消息段
        """
        # 检查消息中是否包含图片
        if not raw_message.get("attachments"):
            return None

        for attachment in raw_message.get("attachments", []):
            if attachment.get("content_type", "").startswith("image/"):
                return Seg(
                    type="image",
                    data={
                        "file": attachment.get("url"),
                        "url": attachment.get("url"),
                    },
                )
        return None

    async def handle_at_message(self, raw_message: dict, self_id: int, group_id: int) -> Seg | None:
        # sourcery skip: use-named-expression
        """
        处理@消息

        Parameters:
            raw_message: dict: 原始消息
            self_id: int: 机器人ID
            group_id: int: 群ID

        Returns:
            Seg | None: @消息段
        """
        # Discord的@消息在文本中，不需要单独处理
        return None

    async def handle_reply_message(self, raw_message: dict) -> List[Seg] | None:
        """
        处理回复消息
        """
        # 获取引用消息信息
        reference_info = raw_message.get("reference")
        if not reference_info:
            return None
            
        message_id = reference_info.get("message_id")
        user_id = reference_info.get("user_id")
        content = reference_info.get("content")
        
        if not message_id or not user_id:
            logger.warning("获取被引用的消息信息失败")
            return None
            
        # 获取发送者信息
        sender_nickname = None
        if isinstance(raw_message.get("sender"), dict):
            sender_nickname = raw_message["sender"].get("nickname")
            
        # 构造回复消息段
        seg_message = []
        
        # 添加回复前缀
        if not sender_nickname:
            logger.warning("无法获取被引用的人的昵称，返回默认值")
            seg_message.append(Seg(type="text", data="[回复 未知用户："))
        else:
            seg_message.append(Seg(type="text", data=f"[回复<{sender_nickname}:{user_id}>："))
            
        # 添加被引用消息内容
        if content:
            seg_message.append(Seg(type="text", data=content))
        else:
            seg_message.append(Seg(type="text", data="(获取发言内容失败)"))
            
        # 添加回复后缀
        seg_message.append(Seg(type="text", data="]，说："))
        
        return seg_message

    async def handle_notice(self, raw_message: dict) -> None:
        """
        处理通知消息

        Parameters:
            raw_message: dict: 原始消息
        """
        notice_type = raw_message.get("notice_type")
        if notice_type == NoticeType.notify:
            sub_type = raw_message.get("sub_type")
            if sub_type == NoticeType.Notify.poke:
                if not global_config.enable_poke:
                    return None
                poke_seg = await self.handle_poke_notify(raw_message)
                if not poke_seg:
                    return None

                # 构造消息体
                message_base = MessageBase(
                    message_info=BaseMessageInfo(
                        platform=global_config.platform,
                        message_id=str(uuid.uuid4()),
                        time=time.time(),
                        user_info=UserInfo(
                            platform=global_config.platform,
                            user_id=raw_message.get("target_id"),
                            user_nickname=None,
                            user_cardname=None,
                        ),
                        group_info=GroupInfo(
                            platform=global_config.platform,
                            group_id=raw_message.get("group_id"),
                            group_name=None,
                        ),
                        template_info=None,
                        format_info=FormatInfo(
                            content_format=["text", "image", "emoji"],
                            accept_format=["text", "image", "emoji", "reply", "voice", "command"],
                        ),
                    ),
                    message_segment=Seg(
                        type="seglist",
                        data=[poke_seg]
                    ),
                )

                # 发送消息
                await self.message_process(message_base)

    async def handle_poke_notify(self, raw_message: dict) -> Seg | None:
        """
        处理戳一戳通知

        Parameters:
            raw_message: dict: 原始消息

        Returns:
            Seg | None: 戳一戳消息段
        """
        return Seg(
            type="poke",
            data={
                "user_id": raw_message.get("user_id"),
                "target_id": raw_message.get("target_id"),
            },
        )

    async def message_process(self, message_base: MessageBase) -> None:
        """
        处理消息

        Parameters:
            message_base: MessageBase: 消息基类
        """
        if not self.maibot_router:
            logger.error("MaiBot路由器未初始化")
            return None

        try:
            logger.debug(f"从Maibot收到的原始数据: {json.dumps(message_base.to_dict(), ensure_ascii=False, indent=2)}")
            response = await self.maibot_router.send_message(message_base)
            if response:
                logger.debug(f"Maibot响应: {json.dumps(response.to_dict() if hasattr(response, 'to_dict') else response, ensure_ascii=False, indent=2)}")
        except Exception as e:
            logger.error(f"发送消息到MaiBot时出错: {e}")
            return None


recv_handler = RecvHandler()
