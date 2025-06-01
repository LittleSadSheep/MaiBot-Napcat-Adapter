import os
import sys
import tomli
import shutil
from .logger import logger
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class DiscordConfig:
    token: str
    discord_heartbeat: int

@dataclass
class MaiBotServerConfig:
    platform_name: str
    host: str
    port: int

@dataclass
class ChatConfig:
    channel_list_type: str
    channel_list: List[str]
    private_list_type: str
    private_list: List[str]
    ban_user_id: List[str]
    enable_poke: bool

@dataclass
class VoiceConfig:
    use_tts: bool

@dataclass
class DebugConfig:
    level: str

@dataclass
class GlobalConfig:
    discord: DiscordConfig
    maibot_server: MaiBotServerConfig
    chat: ChatConfig
    voice: VoiceConfig
    debug: DebugConfig

    def __init__(self):
        self.platform = "discord"
        self.maibot_host = "localhost"
        self.maibot_port = 8199
        self.discord_token = ""
        self.discord_heartbeat_interval = 30
        self.discord_proxy = ""  # 添加代理配置
        self.channel_list_type = "blacklist"
        self.channel_list = []
        self.private_list_type = "blacklist"
        self.private_list = []
        self.ban_user_id = []
        self.enable_poke = True
        self.use_tts = False
        self.debug_level = "DEBUG"

    def load_config(self, config_path: str = "config.toml") -> None:
        """加载配置文件"""
        try:
            with open(config_path, "rb") as f:  # 使用二进制模式打开文件
                config = tomli.load(f)
                logger.debug(f"原始配置文件内容:\n{config}")

            # 加载Discord配置
            discord_config = config.get("Discord_Server", {})
            self.discord_token = discord_config.get("token", "")
            self.discord_heartbeat_interval = discord_config.get("discord_heartbeat", 30)
            self.discord_proxy = discord_config.get("proxy", "")  # 加载代理配置

            # 加载MaiBot配置
            maibot_config = config.get("MaiBot_Server", {})
            self.platform = maibot_config.get("platform_name", "discord")
            self.maibot_host = maibot_config.get("host", "localhost")
            self.maibot_port = maibot_config.get("port", 8199)

            # 加载聊天配置
            chat_config = config.get("Chat", {})
            self.channel_list_type = chat_config.get("channel_list_type", "blacklist")
            self.channel_list = chat_config.get("channel_list", [])
            self.private_list_type = chat_config.get("private_list_type", "blacklist")
            self.private_list = chat_config.get("private_list", [])
            self.ban_user_id = chat_config.get("ban_user_id", [])
            self.enable_poke = chat_config.get("enable_poke", True)

            # 加载语音配置
            voice_config = config.get("Voice", {})
            self.use_tts = voice_config.get("use_tts", False)

            # 加载调试配置
            debug_config = config.get("Debug", {})
            self.debug_level = debug_config.get("level", "DEBUG")

            logger.debug(f"读取到的配置内容：")
            logger.debug(f"平台: {self.platform}")
            logger.debug(f"MaiBot服务器地址: {self.maibot_host}:{self.maibot_port}")
            logger.debug(f"Discord Token: {self.discord_token}")
            logger.debug(f"Discord代理: {self.discord_proxy}")  # 添加代理日志
            logger.debug(f"心跳间隔: {self.discord_heartbeat_interval}秒")
            logger.debug(f"频道列表类型: {self.channel_list_type}")
            logger.debug(f"频道列表: {self.channel_list}")
            logger.debug(f"私聊列表类型: {self.private_list_type}")
            logger.debug(f"私聊列表: {self.private_list}")
            logger.debug(f"禁用用户ID列表: {self.ban_user_id}")
            logger.debug(f"是否启用TTS: {self.use_tts}")
            logger.debug(f"调试级别: {self.debug_level}")

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise


# 加载全局配置
global_config = GlobalConfig()
global_config.load_config()
