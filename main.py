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

# 创建Discord Bot客户端
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Bot已登录为 {bot.user.name}')
    recv_handler.bot = bot
    send_handler.bot = bot

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # 获取消息类型和频道信息
    message_type = "private" if isinstance(message.channel, discord.DMChannel) else "group"
    channel_info = f"私聊" if message_type == "private" else f"频道 {message.channel.name} (ID: {message.channel.id})"
    
    logger.info(f"收到Discord消息:")
    logger.info(f"- 消息类型: {message_type}")
    logger.info(f"- 消息ID: {message.id}")
    logger.info(f"- 发送者: {message.author.name} (ID: {message.author.id})")
    logger.info(f"- 频道: {channel_info}")
    logger.info(f"- 内容: {message.content}")

    # 消息回显
    echo_content = f"收到消息：\n"
    echo_content += f"发送者：{message.author.name}\n"
    echo_content += f"内容：{message.content}\n"
    if message.attachments:
        echo_content += f"附件：{len(message.attachments)}个\n"
    if message.embeds:
        echo_content += f"嵌入：{len(message.embeds)}个\n"
    
    try:
        await message.channel.send(echo_content)
        logger.info("消息回显已发送")
    except Exception as e:
        logger.error(f"发送消息回显时出错: {e}")

    # 将Discord消息转换为MaiBot消息格式
    discord_message = {
        "post_type": "message",
        "message_type": message_type,
        "message_id": str(message.id),
        "time": message.created_at.timestamp(),
        "self_id": str(bot.user.id),
        "sender": {
            "user_id": str(message.author.id),
            "nickname": message.author.name,
            "card": message.author.display_name
        }
    }

    if isinstance(message.channel, discord.TextChannel):
        discord_message["group_id"] = str(message.channel.id)
        discord_message["group_name"] = message.channel.name
        logger.info(f"- 群组ID: {message.channel.id}")
        logger.info(f"- 群组名称: {message.channel.name}")
    else:
        logger.info("- 群组ID: 无（私聊消息）")

    # 处理消息内容
    content = []
    
    # 处理引用消息
    if message.reference and message.reference.resolved:
        content.append({
            "type": "reply",
            "data": {
                "id": str(message.reference.message_id)
            }
        })
        logger.info(f"- 引用消息ID: {message.reference.message_id}")
    
    # 处理消息内容
    if message.content:
        # 处理提及
        for mention in message.mentions:
            content.append({
                "type": "mention",
                "data": {
                    "name": mention.name
                }
            })
            logger.info(f"- 提及用户: {mention.name} (ID: {mention.id})")
        
        # 处理文本内容
        content.append({
            "type": "text",
            "data": {
                "text": message.content
            }
        })
    
    # 处理表情
    for emoji in message.emojis:
        content.append({
            "type": "emoji",
            "data": {
                "emoji": str(emoji)
            }
        })
        logger.info(f"- 表情: {emoji}")
    
    # 处理附件
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith('image/'):
            content.append({
                "type": "image",
                "data": {
                    "file": attachment.url
                }
            })
            logger.info(f"- 图片附件: {attachment.url}")

    discord_message["message"] = content
    logger.info(f"转换后的消息格式: {json.dumps(discord_message, ensure_ascii=False)}")
    await message_queue.put(discord_message)
    logger.info("消息已放入队列")

async def message_process():
    while True:
        try:
            message = await message_queue.get()
            logger.info(f"从队列中获取到消息: {json.dumps(message, ensure_ascii=False)}")
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
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            logger.exception("详细错误信息：")
        await asyncio.sleep(0.05)

async def main():
    recv_handler.maibot_router = router
    _ = await asyncio.gather(
        bot.start(global_config.discord_token),
        mmc_start_com(),
        message_process(),
        check_timeout_response()
    )

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
