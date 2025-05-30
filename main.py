import asyncio
import sys
import json
import discord
from discord.ext import commands
from src.logger import logger
from src.recv_handler import recv_handler
from src.send_handler import send_handler
from src.config import global_config
from src.mmc_com_layer import mmc_start_com, mmc_stop_com, router
from src.message_queue import message_queue, put_response, check_timeout_response

# 创建Discord客户端
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Discord Bot已登录为 {bot.user.name}')
    recv_handler.discord_bot = bot
    send_handler.discord_bot = bot

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # 检查频道/私聊黑白名单
    if isinstance(message.channel, discord.TextChannel):
        if global_config.channel_list_type == "whitelist" and str(message.channel.id) not in global_config.channel_list:
            return
        if global_config.channel_list_type == "blacklist" and str(message.channel.id) in global_config.channel_list:
            return
    else:
        if global_config.private_list_type == "whitelist" and str(message.author.id) not in global_config.private_list:
            return
        if global_config.private_list_type == "blacklist" and str(message.author.id) in global_config.private_list:
            return
    
    # 检查全局禁用名单
    if str(message.author.id) in global_config.ban_user_id:
        return
    
    # 将Discord消息转换为MaiBot格式
    discord_message = {
        "post_type": "message",
        "message_type": "group" if isinstance(message.channel, discord.TextChannel) else "private",
        "message_id": str(message.id),
        "user_id": str(message.author.id),
        "group_id": str(message.channel.id) if isinstance(message.channel, discord.TextChannel) else None,
        "message": message.content,
        "raw_message": message.content,
        "sender": {
            "user_id": str(message.author.id),
            "nickname": message.author.display_name,
            "card": message.author.name
        }
    }
    
    await message_queue.put(discord_message)

async def message_process():
    while True:
        message = await message_queue.get()
        post_type = message.get("post_type")
        if post_type == "message":
            await recv_handler.handle_raw_message(message)
        elif post_type == "meta_event":
            await recv_handler.handle_meta_event(message)
        elif post_type == "notice":
            await recv_handler.handle_notice(message)
        else:
            logger.warning(f"未知的post_type: {post_type}")
        message_queue.task_done()
        await asyncio.sleep(0.05)

async def main():
    recv_handler.maibot_router = router
    _ = await asyncio.gather(
        discord_client(),
        mmc_start_com(),
        message_process(),
        check_timeout_response()
    )

async def discord_client():
    logger.info("正在启动Discord客户端...")
    try:
        await bot.start(global_config.discord_token)
    except Exception as e:
        logger.error(f"Discord客户端启动失败: {e}")
        raise

async def graceful_shutdown():
    try:
        logger.info("正在关闭adapter...")
        await mmc_stop_com()
        await bot.close()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"Adapter关闭中出现错误: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.warning("收到中断信号，正在优雅关闭...")
        loop.run_until_complete(graceful_shutdown())
    except Exception as e:
        logger.exception(f"主程序异常: {str(e)}")
        sys.exit(1)
    finally:
        if loop and not loop.is_closed():
            loop.close()
        sys.exit(0)
