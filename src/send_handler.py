import json
import websockets as Server
import uuid
from maim_message import (
    UserInfo,
    GroupInfo,
    Seg,
    BaseMessageInfo,
    MessageBase,
)
from typing import Dict, Any, Tuple
import discord

from . import CommandType
from .config import global_config
from .message_queue import get_response
from .logger import logger
from .utils import get_image_format, convert_image_to_gif


class SendHandler:
    def __init__(self):
        self.server_connection: Server.ServerConnection = None
        self.discord_bot = None  # Assuming a Discord bot is set up

    async def handle_message(self, raw_message_base_dict: dict) -> None:
        raw_message_base: MessageBase = MessageBase.from_dict(raw_message_base_dict)
        message_segment: Seg = raw_message_base.message_segment
        logger.info("接收到来自MaiBot的消息，处理中")
        logger.debug(f"来自MaiBot的原始消息: {json.dumps(raw_message_base_dict, ensure_ascii=False)}")
        if message_segment.type == "command":
            return await self.send_command(raw_message_base)
        else:
            return await self.send_normal_message(raw_message_base)

    async def send_normal_message(self, message: MessageBase) -> None:
        """
        发送普通消息

        Parameters:
            message: MessageBase: 消息基类
        """
        if not message.message_segment:
            return None

        # 获取消息内容
        content = ""
        embeds = []
        message_reference = None
        attachments = []

        # 处理消息段
        if message.message_segment.type == "seglist":
            for seg in message.message_segment.data:
                if seg.type == "reply":
                    message_reference = {
                        "message_id": seg.data,
                        "channel_id": message.message_info.group_info.group_id if message.message_info.group_info else None,
                        "guild_id": message.message_info.group_info.group_id if message.message_info.group_info else None
                    }
                elif seg.type == "text":
                    content += seg.data
                elif seg.type == "image":
                    # 处理图片，添加到attachments
                    attachments.append({
                        "id": str(uuid.uuid4()),
                        "filename": f"image_{uuid.uuid4()}.png",
                        "content_type": "image/png",
                        "size": len(seg.data),
                        "url": seg.data,
                        "proxy_url": seg.data,
                        "height": None,
                        "width": None
                    })
                elif seg.type == "emoji":
                    # 处理表情，添加到embeds
                    embeds.append({
                        "type": "image",
                        "url": seg.data,
                        "image": {
                            "url": seg.data,
                            "proxy_url": seg.data
                        }
                    })
        else:
            if message.message_segment.type == "reply":
                message_reference = {
                    "message_id": message.message_segment.data,
                    "channel_id": message.message_info.group_info.group_id if message.message_info.group_info else None,
                    "guild_id": message.message_info.group_info.group_id if message.message_info.group_info else None
                }
            elif message.message_segment.type == "text":
                content = message.message_segment.data
            elif message.message_segment.type == "image":
                attachments.append({
                    "id": str(uuid.uuid4()),
                    "filename": f"image_{uuid.uuid4()}.png",
                    "content_type": "image/png",
                    "size": len(message.message_segment.data),
                    "url": message.message_segment.data,
                    "proxy_url": message.message_segment.data,
                    "height": None,
                    "width": None
                })
            elif message.message_segment.type == "emoji":
                embeds.append({
                    "type": "image",
                    "url": message.message_segment.data,
                    "image": {
                        "url": message.message_segment.data,
                        "proxy_url": message.message_segment.data
                    }
                })

        # 构建Discord消息体
        payload = {
            "content": content,
            "embeds": embeds,
            "attachments": attachments,
            "message_reference": message_reference if message_reference else None,
            "tts": False,
            "flags": 0
        }

        logger.debug(f"发送给Discord的原始消息: {json.dumps(payload, ensure_ascii=False)}")

        # 发送消息
        if message.message_info.group_info:
            # 群消息
            await self.send_group_message(
                message.message_info.group_info.group_id,
                payload
            )
        else:
            # 私聊消息
            await self.send_private_message(
                message.message_info.user_info.user_id,
                payload
            )

    async def send_command(self, raw_message_base: MessageBase) -> None:
        """
        处理命令类
        """
        logger.info("处理命令中")
        message_info: BaseMessageInfo = raw_message_base.message_info
        message_segment: Seg = raw_message_base.message_segment
        group_info: GroupInfo = message_info.group_info
        seg_data: Dict[str, Any] = message_segment.data
        command_name: str = seg_data.get("name")
        try:
            match command_name:
                case CommandType.GROUP_BAN.name:
                    command, args_dict = self.handle_ban_command(seg_data.get("args"), group_info)
                case CommandType.GROUP_WHOLE_BAN.name:
                    command, args_dict = self.handle_whole_ban_command(seg_data.get("args"), group_info)
                case CommandType.GROUP_KICK.name:
                    command, args_dict = self.handle_kick_command(seg_data.get("args"), group_info)
                case _:
                    logger.error(f"未知命令: {command_name}")
                    return
        except Exception as e:
            logger.error(f"处理命令时发生错误: {e}")
            return None

        if not command or not args_dict:
            logger.error("命令或参数缺失")
            return None

        response = await self.send_message_to_napcat(command, args_dict)
        if response.get("status") == "ok":
            logger.info(f"命令 {command_name} 执行成功")
        else:
            logger.warning(f"命令 {command_name} 执行失败，napcat返回：{str(response)}")

    def get_level(self, seg_data: Seg) -> int:
        if seg_data.type == "seglist":
            return 1 + max(self.get_level(seg) for seg in seg_data.data)
        else:
            return 1

    async def handle_seg_recursive(self, seg_data: Seg) -> str:
        if seg_data.type == "seglist":
            if not seg_data.data:
                return ""
            messages = []
            for seg in seg_data.data:
                message = await self.process_message_by_type(seg)
                if message:
                    messages.append(message)
            return " ".join(messages)
        else:
            return await self.process_message_by_type(seg_data)

    async def process_message_by_type(self, seg: Seg) -> str:
        if seg.type == "text":
            return seg.data
        elif seg.type == "image":
            # 对于图片，我们返回图片的URL
            if isinstance(seg.data, dict):
                return seg.data.get("url", "")
            return ""
        elif seg.type == "emoji":
            # 对于表情，我们返回表情的文本表示
            return seg.data
        elif seg.type == "reply":
            # 对于回复，我们返回引用的消息ID
            return f"回复消息ID: {seg.data}"
        return ""

    def build_payload(self, payload: list, addon: dict, is_reply: bool = False) -> list:
        # sourcery skip: for-append-to-extend, merge-list-append, simplify-generator
        """构建发送的消息体"""
        if is_reply:
            temp_list = []
            temp_list.append(addon)
            for i in payload:
                if i.get("type") == "reply":
                    logger.debug("检测到多个回复，使用最新的回复")
                    continue
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

    def handle_ban_command(self, args: Dict[str, Any], group_info: GroupInfo) -> Tuple[str, Dict[str, Any]]:
        """处理封禁命令

        Args:
            args (Dict[str, Any]): 参数字典
            group_info (GroupInfo): 群聊信息（对应目标群聊）

        Returns:
            Tuple[CommandType, Dict[str, Any]]
        """
        duration: int = int(args["duration"])
        user_id: int = int(args["qq_id"])
        group_id: int = int(group_info.group_id)
        if duration <= 0:
            raise ValueError("封禁时间必须大于0")
        if not user_id or not group_id:
            raise ValueError("封禁命令缺少必要参数")
        if duration > 2592000:
            raise ValueError("封禁时间不能超过30天")
        return (
            CommandType.GROUP_BAN.value,
            {
                "group_id": group_id,
                "user_id": user_id,
                "duration": duration,
            },
        )

    def handle_whole_ban_command(self, args: Dict[str, Any], group_info: GroupInfo) -> Tuple[str, Dict[str, Any]]:
        """处理全体禁言命令

        Args:
            args (Dict[str, Any]): 参数字典
            group_info (GroupInfo): 群聊信息（对应目标群聊）

        Returns:
            Tuple[CommandType, Dict[str, Any]]
        """
        enable = args["enable"]
        assert isinstance(enable, bool), "enable参数必须是布尔值"
        group_id: int = int(group_info.group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")
        return (
            CommandType.GROUP_WHOLE_BAN.value,
            {
                "group_id": group_id,
                "enable": enable,
            },
        )
    
    def handle_kick_command(self, args: Dict[str, Any], group_info: GroupInfo) -> Tuple[str, Dict[str, Any]]:
        """处理群成员踢出命令

        Args:
            args (Dict[str, Any]): 参数字典
            group_info (GroupInfo): 群聊信息（对应目标群聊）

        Returns:
            Tuple[CommandType, Dict[str, Any]]
        """
        user_id: int = int(args["qq_id"])
        group_id: int = int(group_info.group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")
        if user_id <= 0:
            raise ValueError("用户ID无效")
        return (
            CommandType.GROUP_KICK.value,
            {
                "group_id": group_id,
                "user_id": user_id,
                "reject_add_request": False,  # 不拒绝加群请求
            },
        )
    
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

    async def send_group_message(self, channel_id: str, payload: dict) -> None:
        """
        发送群消息

        Parameters:
            channel_id: str: 频道ID
            payload: dict: 消息内容
        """
        try:
            channel = self.discord_bot.get_channel(int(channel_id))
            if not channel:
                logger.error(f"找不到频道: {channel_id}")
                return

            # 处理回复消息
            reference = None
            if payload.get("message_reference"):
                try:
                    ref_msg = await channel.fetch_message(int(payload["message_reference"]["message_id"]))
                    reference = ref_msg
                except Exception as e:
                    logger.error(f"获取引用消息失败: {e}")

            # 处理附件
            files = []
            if payload.get("attachments"):
                for attachment in payload["attachments"]:
                    try:
                        # 这里需要实现从URL下载图片的逻辑
                        # 暂时跳过
                        pass
                    except Exception as e:
                        logger.error(f"处理附件失败: {e}")

            # 处理嵌入内容
            embeds = []
            if payload.get("embeds"):
                for embed_data in payload["embeds"]:
                    try:
                        embed = discord.Embed()
                        if embed_data.get("type") == "image":
                            embed.set_image(url=embed_data["url"])
                        embeds.append(embed)
                    except Exception as e:
                        logger.error(f"处理嵌入内容失败: {e}")

            # 发送消息
            await channel.send(
                content=payload.get("content", ""),
                reference=reference,
                embeds=embeds,
                files=files
            )
            logger.info(f"成功发送消息到频道 {channel_id}")
        except Exception as e:
            logger.error(f"发送群消息失败: {e}")

    async def send_private_message(self, user_id: str, payload: dict) -> None:
        """
        发送私聊消息

        Parameters:
            user_id: str: 用户ID
            payload: dict: 消息内容
        """
        try:
            user = await self.discord_bot.fetch_user(int(user_id))
            if not user:
                logger.error(f"找不到用户: {user_id}")
                return

            # 处理附件
            files = []
            if payload.get("attachments"):
                for attachment in payload["attachments"]:
                    try:
                        # 这里需要实现从URL下载图片的逻辑
                        # 暂时跳过
                        pass
                    except Exception as e:
                        logger.error(f"处理附件失败: {e}")

            # 处理嵌入内容
            embeds = []
            if payload.get("embeds"):
                for embed_data in payload["embeds"]:
                    try:
                        embed = discord.Embed()
                        if embed_data.get("type") == "image":
                            embed.set_image(url=embed_data["url"])
                        embeds.append(embed)
                    except Exception as e:
                        logger.error(f"处理嵌入内容失败: {e}")

            # 发送消息
            await user.send(
                content=payload.get("content", ""),
                embeds=embeds,
                files=files
            )
            logger.info(f"成功发送私聊消息给用户 {user_id}")
        except Exception as e:
            logger.error(f"发送私聊消息失败: {e}")


send_handler = SendHandler()
