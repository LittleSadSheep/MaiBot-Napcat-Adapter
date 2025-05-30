import os
import sys
import tomllib
import shutil
from .logger import logger, set_log_level
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class Config:
    # Discord配置
    discord_token: str
    heartbeat: int = 30

    # MaiBot配置
    platform: str = "discord"  # 平台标识符
    maibot_host: str = "localhost"
    maibot_port: int = 8199

    # 聊天配置
    channel_list_type: str = "blacklist"
    channel_list: List[int] = None
    private_list_type: str = "blacklist"
    private_list: List[int] = None
    ban_user_id: List[int] = None
    enable_poke: bool = True

    # 语音配置
    use_tts: bool = False

    # 调试配置
    debug_level: str = "INFO"

    def __post_init__(self):
        if self.channel_list is None:
            self.channel_list = []
        if self.private_list is None:
            self.private_list = []
        if self.ban_user_id is None:
            self.ban_user_id = []

    def _get_config_path(self):
        current_file_path = os.path.abspath(__file__)
        src_path = os.path.dirname(current_file_path)
        self.root_path = os.path.join(src_path, "..")
        self.config_path = os.path.join(self.root_path, "config.toml")

    def load_config(self):
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
                config_data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                logger.critical(f"配置文件bot_config.toml填写有误，请检查第{e.lineno}行第{e.colno}处：{e.msg}")
                sys.exit(1)

        # Discord配置
        self.discord_token = config_data["Discord"]["token"]
        self.heartbeat = config_data["Discord"].get("heartbeat", 30)

        # MaiBot配置
        self.platform = config_data["MaiBot_Server"]["platform_name"]
        self.maibot_host = config_data["MaiBot_Server"]["host"]
        self.maibot_port = config_data["MaiBot_Server"]["port"]

        # 聊天配置
        self.channel_list_type = config_data["Chat"]["channel_list_type"]
        self.channel_list = config_data["Chat"]["channel_list"]
        self.private_list_type = config_data["Chat"]["private_list_type"]
        self.private_list = config_data["Chat"]["private_list"]
        self.ban_user_id = config_data["Chat"]["ban_user_id"]
        self.enable_poke = config_data["Chat"]["enable_poke"]

        # 语音配置
        self.use_tts = config_data["Voice"]["use_tts"]

        # 调试配置
        self.debug_level = config_data["Debug"]["level"]

        if self.debug_level == "DEBUG":
            logger.debug("原始配置文件内容:")
            logger.debug(config_data)
            logger.debug("读取到的配置内容：")
            logger.debug(f"平台: {self.platform}")
            logger.debug(f"MaiBot服务器地址: {self.maibot_host}:{self.maibot_port}")
            logger.debug(f"Discord Token: {self.discord_token}")
            logger.debug(f"心跳间隔: {self.heartbeat}秒")
            logger.debug(f"频道列表类型: {self.channel_list_type}")
            logger.debug(f"频道列表: {self.channel_list}")
            logger.debug(f"私聊列表类型: {self.private_list_type}")
            logger.debug(f"私聊列表: {self.private_list}")
            logger.debug(f"禁用用户ID列表: {self.ban_user_id}")
            logger.debug(f"是否启用TTS: {self.use_tts}")
            logger.debug(f"调试级别: {self.debug_level}")


def load_config() -> Config:
    try:
        with open("config.toml", "rb") as f:
            config_data = tomllib.load(f)
        
        # 设置日志级别
        debug_level = config_data.get("Debug", {}).get("level", "INFO")
        set_log_level(debug_level)
        
        # 创建配置对象
        config = Config(
            discord_token=config_data["Discord"]["token"],
            heartbeat=config_data["Discord"].get("heartbeat", 30),
            maibot_host=config_data["MaiBot_Server"]["host"],
            maibot_port=config_data["MaiBot_Server"]["port"],
            channel_list_type=config_data["Chat"]["channel_list_type"],
            channel_list=config_data["Chat"]["channel_list"],
            private_list_type=config_data["Chat"]["private_list_type"],
            private_list=config_data["Chat"]["private_list"],
            ban_user_id=config_data["Chat"]["ban_user_id"],
            enable_poke=config_data["Chat"]["enable_poke"],
            use_tts=config_data["Voice"]["use_tts"],
            debug_level=debug_level
        )
        
        logger.info("配置加载成功")
        return config
    except Exception as e:
        logger.error(f"加载配置时出错: {e}")
        raise

global_config = load_config()
