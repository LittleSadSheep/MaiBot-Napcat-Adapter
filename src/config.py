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

    @classmethod
    def load_from_toml(cls, toml_path: str) -> 'GlobalConfig':
        with open(toml_path, 'rb') as f:
            config_dict = tomli.load(f)
        
        return cls(
            discord=DiscordConfig(
                token=config_dict['Discord']['token'],
                discord_heartbeat=config_dict['Discord']['discord_heartbeat']
            ),
            maibot_server=MaiBotServerConfig(
                platform_name=config_dict['MaiBot_Server']['platform_name'],
                host=config_dict['MaiBot_Server']['host'],
                port=config_dict['MaiBot_Server']['port']
            ),
            chat=ChatConfig(
                channel_list_type=config_dict['Chat']['channel_list_type'],
                channel_list=config_dict['Chat']['channel_list'],
                private_list_type=config_dict['Chat']['private_list_type'],
                private_list=config_dict['Chat']['private_list'],
                ban_user_id=config_dict['Chat']['ban_user_id'],
                enable_poke=config_dict['Chat']['enable_poke']
            ),
            voice=VoiceConfig(
                use_tts=config_dict['Voice']['use_tts']
            ),
            debug=DebugConfig(
                level=config_dict['Debug']['level']
            )
        )


class Config:
    platform: str = "discord"
    nickname: Optional[str] = None
    server_host: str = "localhost"
    server_port: int = 8095
    discord_heartbeat_interval: int = 30

    def __init__(self):
        self._get_config_path()

    def _get_config_path(self):
        current_file_path = os.path.abspath(__file__)
        src_path = os.path.dirname(current_file_path)
        self.root_path = os.path.join(src_path, "..")
        self.config_path = os.path.join(self.root_path, "config.toml")

    def load_config(self):  # sourcery skip: extract-method, move-assign
        include_configs = ["Discord_Server", "MaiBot_Server", "Chat", "Voice", "Debug"]
        if not os.path.exists(self.config_path):
            logger.error("配置文件不存在！")
            logger.info("正在创建配置文件...")
            shutil.copy(
                os.path.join(self.root_path, "template", "template_config.toml"),
                os.path.join(self.root_path, "config.toml"),
            )
            logger.info("配置文件创建成功，请修改配置文件后重启程序。")
            sys.exit(1)
        with open(self.config_path, "rb") as f:
            try:
                raw_config = tomli.load(f)
            except tomli.TOMLDecodeError as e:
                logger.critical(f"配置文件bot_config.toml填写有误，请检查第{e.lineno}行第{e.colno}处：{e.msg}")
                sys.exit(1)
        for key in include_configs:
            if key not in raw_config:
                logger.error(f"配置文件中缺少必需的字段: '{key}'")
                logger.error("你的配置文件可能过时，请尝试手动更新配置文件。")
                sys.exit(1)

        self.server_host = raw_config["Discord_Server"].get("host", "localhost")
        self.server_port = raw_config["Discord_Server"].get("port", 8095)
        self.discord_heartbeat_interval = raw_config["Discord_Server"].get("heartbeat", 30)
        self.discord_token = raw_config["Discord_Server"].get("token", "")

        self.mai_host = raw_config["MaiBot_Server"].get("host", "localhost")
        self.mai_port = raw_config["MaiBot_Server"].get("port", 8000)
        self.platform = raw_config["MaiBot_Server"].get("platform_name")
        if not self.platform:
            logger.critical("请在配置文件中指定平台")
            sys.exit(1)

        self.channel_list_type: str = raw_config["Chat"].get("channel_list_type")
        self.channel_list: list = raw_config["Chat"].get("channel_list", [])
        self.private_list_type: str = raw_config["Chat"].get("private_list_type")
        self.private_list: list = raw_config["Chat"].get("private_list", [])
        self.ban_user_id: list = raw_config["Chat"].get("ban_user_id", [])
        self.enable_poke: bool = raw_config["Chat"].get("enable_poke", True)
        if self.channel_list_type not in ["whitelist", "blacklist"]:
            logger.critical("请在配置文件中指定channel_list_type或channel_list_type填写错误")
            sys.exit(1)
        if self.private_list_type not in ["whitelist", "blacklist"]:
            logger.critical("请在配置文件中指定private_list_type或private_list_type填写错误")
            sys.exit(1)

        self.use_tts = raw_config["Voice"].get("use_tts", False)

        self.debug_level = raw_config["Debug"].get("level", "INFO")
        if self.debug_level == "DEBUG":
            logger.debug("原始配置文件内容:")
            logger.debug(raw_config)
            logger.debug("读取到的配置内容：")
            logger.debug(f"平台: {self.platform}")
            logger.debug(f"MaiBot服务器地址: {self.mai_host}:{self.mai_port}")
            logger.debug(f"Discord Token: {self.discord_token}")
            logger.debug(f"心跳间隔: {self.discord_heartbeat_interval}秒")
            logger.debug(f"频道列表类型: {self.channel_list_type}")
            logger.debug(f"频道列表: {self.channel_list}")
            logger.debug(f"私聊列表类型: {self.private_list_type}")
            logger.debug(f"私聊列表: {self.private_list}")
            logger.debug(f"禁用用户ID列表: {self.ban_user_id}")
            logger.debug(f"是否启用TTS: {self.use_tts}")
            logger.debug(f"调试级别: {self.debug_level}")


# 加载全局配置
global_config = Config()
global_config.load_config()
