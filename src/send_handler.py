import json
import websockets as Server
import uuid
import discord
from typing import List, Optional

from .config import global_config

# 白名单机制不启用
from .message_queue import get_response
from .logger import logger

from maim_message import (
    UserInfo,
    GroupInfo,
    Seg,
    BaseMessageInfo,
    MessageBase,
)

from .utils import get_image_format, convert_image_to_gif


class SendHandler:
    bot: discord.Client = None

    async def send_message(self, message: MessageBase) -> None:
        """
        发送消息到Discord
        Parameters:
            message: MessageBase: 消息对象
        """
        try:
            channel_id = message.message_info.group_info.group_id if message.message_info.group_info else None
            if channel_id:
                channel = self.bot.get_channel(int(channel_id))
            else:
                user_id = message.message_info.user_info.user_id
                user = await self.bot.fetch_user(int(user_id))
                channel = user.dm_channel or await user.create_dm()

            if not channel:
                logger.error(f"无法找到目标频道或用户: {channel_id or user_id}")
                return

            # 处理消息内容
            content = await self._process_message_content(message.message_segment)
            
            # 发送消息
            await channel.send(content=content)
            logger.info(f"消息已发送到 {channel_id or user_id}")

        except Exception as e:
            logger.error(f"发送消息时出错: {str(e)}")

    async def _process_message_content(self, segment: Seg) -> str:
        """
        处理消息内容
        Parameters:
            segment: Seg: 消息段
        Returns:
            str: 处理后的消息内容
        """
        if segment.type == "text":
            return segment.data.get("text", "")
        elif segment.type == "image":
            return f"[图片] {segment.data.get('file', '')}"
        elif segment.type == "emoji":
            return segment.data.get("emoji", "")
        elif segment.type == "reply":
            return f"[回复消息ID: {segment.data.get('id', '')}]"
        elif segment.type == "seglist":
            content_parts = []
            for sub_segment in segment.data:
                content = await self._process_message_content(sub_segment)
                if content:
                    content_parts.append(content)
            return "\n".join(content_parts)
        else:
            logger.warning(f"不支持的消息类型: {segment.type}")
            return ""

    def get_level(self, seg_data: Seg) -> int:
        if seg_data.type == "seglist":
            return 1 + max(self.get_level(seg) for seg in seg_data.data)
        else:
            return 1

    async def handle_seg_recursive(self, seg_data: Seg) -> list:
        payload: list = []
        if seg_data.type == "seglist":
            # level = self.get_level(seg_data)  # 给以后可能的多层嵌套做准备，此处不使用
            if not seg_data.data:
                return []
            for seg in seg_data.data:
                payload = self.process_message_by_type(seg, payload)
        else:
            payload = self.process_message_by_type(seg_data, payload)
        return payload

    def process_message_by_type(self, seg: Seg, payload: list) -> list:
        # sourcery skip: reintroduce-else, swap-if-else-branches, use-named-expression
        new_payload = payload
        if seg.type == "reply":
            target_id = seg.data
            if target_id == "notice":
                return []
            new_payload = self.build_payload(payload, self.handle_reply_message(target_id), True)
        elif seg.type == "text":
            text = seg.data
            if not text:
                return []
            new_payload = self.build_payload(payload, self.handle_text_message(text), False)
        elif seg.type == "face":
            pass
        elif seg.type == "image":
            image = seg.data
            new_payload = self.build_payload(payload, self.handle_image_message(image), False)
        elif seg.type == "emoji":
            emoji = seg.data
            new_payload = self.build_payload(payload, self.handle_emoji_message(emoji), False)
        elif seg.type == "voice":
            voice = seg.data
            new_payload = self.build_payload(payload, self.handle_voice_message(voice), False)
        return new_payload

    def build_payload(self, payload: list, addon: dict, is_reply: bool = False) -> list:
        # sourcery skip: for-append-to-extend, merge-list-append, simplify-generator
        """构建发送的消息体"""
        if is_reply:
            temp_list = []
            temp_list.append(addon)
            for i in payload:
                temp_list.append(i)
            return temp_list
        else:
            payload.append(addon)
            return payload

    def handle_reply_message(self, id: str) -> dict:
        """处理回复消息"""
        return {"type": "reply", "data": {"id": id}}

    def handle_text_message(self, message: str) -> dict:
        """处理文本消息"""
        return {"type": "text", "data": {"text": message}}

    def handle_image_message(self, encoded_image: str) -> dict:
        """处理图片消息"""
        return {
            "type": "image",
            "data": {
                "file": f"base64://{encoded_image}",
                "subtype": 0,
            },
        }  # base64 编码的图片

    def handle_emoji_message(self, encoded_emoji: str) -> dict:
        """处理表情消息"""
        encoded_image = encoded_emoji
        image_format = get_image_format(encoded_emoji)
        if image_format != "gif":
            encoded_image = convert_image_to_gif(encoded_emoji)
        return {
            "type": "image",
            "data": {
                "file": f"base64://{encoded_image}",
                "subtype": 1,
                "summary": "[动画表情]",
            },
        }

    def handle_voice_message(self, encoded_voice: str) -> dict:
        """处理语音消息"""
        if not global_config.use_tts:
            logger.warning("未启用语音消息处理")
            return {}
        if not encoded_voice:
            return {}
        return {
            "type": "record",
            "data": {"file": f"base64://{encoded_voice}"},
        }

    async def send_message_to_napcat(self, action: str, params: dict) -> dict:
        request_uuid = str(uuid.uuid4())
        payload = json.dumps({"action": action, "params": params, "echo": request_uuid})
        await self.server_connection.send(payload)
        try:
            response = await get_response(request_uuid)
        except TimeoutError:
            logger.error("发送消息超时，未收到响应")
            return {"status": "error", "message": "timeout"}
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return {"status": "error", "message": str(e)}
        return response


send_handler = SendHandler()
