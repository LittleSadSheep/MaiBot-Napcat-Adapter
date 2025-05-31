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
    
    # 获取消息引用信息
    reference_info = None
    if message.reference:
        try:
            referenced_message = await message.channel.fetch_message(message.reference.message_id)
            reference_info = {
                "message_id": str(referenced_message.id),
                "user_id": str(referenced_message.author.id),
                "content": referenced_message.content,
                "timestamp": referenced_message.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"获取引用消息失败: {e}")
    
    # 获取消息附件信息
    attachments = []
    for attachment in message.attachments:
        attachments.append({
            "id": str(attachment.id),
            "filename": attachment.filename,
            "url": attachment.url,
            "content_type": attachment.content_type,
            "size": attachment.size
        })
    
    # 获取消息嵌入信息
    embeds = []
    for embed in message.embeds:
        embed_data = {
            "title": embed.title,
            "description": embed.description,
            "url": embed.url,
            "color": embed.color.value if embed.color else None,
            "timestamp": embed.timestamp.isoformat() if embed.timestamp else None,
            "footer": {
                "text": embed.footer.text if embed.footer else None,
                "icon_url": embed.footer.icon_url if embed.footer else None
            } if embed.footer else None,
            "image": {
                "url": embed.image.url if embed.image else None
            } if embed.image else None,
            "thumbnail": {
                "url": embed.thumbnail.url if embed.thumbnail else None
            } if embed.thumbnail else None,
            "author": {
                "name": embed.author.name if embed.author else None,
                "url": embed.author.url if embed.author else None,
                "icon_url": embed.author.icon_url if embed.author else None
            } if embed.author else None,
            "fields": [
                {
                    "name": field.name,
                    "value": field.value,
                    "inline": field.inline
                } for field in embed.fields
            ] if embed.fields else []
        }
        embeds.append(embed_data)
    
    # 获取消息组件信息
    components = []
    if message.components:
        for component in message.components:
            if isinstance(component, discord.ui.ActionRow):
                for child in component.children:
                    if isinstance(child, discord.ui.Button):
                        components.append({
                            "type": "button",
                            "label": child.label,
                            "style": str(child.style),
                            "custom_id": child.custom_id,
                            "url": child.url,
                            "disabled": child.disabled
                        })
                    elif isinstance(child, discord.ui.Select):
                        components.append({
                            "type": "select",
                            "custom_id": child.custom_id,
                            "placeholder": child.placeholder,
                            "min_values": child.min_values,
                            "max_values": child.max_values,
                            "options": [
                                {
                                    "label": option.label,
                                    "value": option.value,
                                    "description": option.description,
                                    "default": option.default
                                } for option in child.options
                            ]
                        })
    
    # 将Discord消息转换为MaiBot格式
    discord_message = {
        "post_type": "message",
        "message_type": "group" if isinstance(message.channel, discord.TextChannel) else "private",
        "message_id": str(message.id),
        "user_id": str(message.author.id),
        "group_id": str(message.channel.id) if isinstance(message.channel, discord.TextChannel) else None,
        "message": message.content,
        "raw_message": message.content,
        "timestamp": message.created_at.isoformat(),
        "edited_timestamp": message.edited_at.isoformat() if message.edited_at else None,
        "tts": message.tts,
        "mention_everyone": message.mention_everyone,
        "mentions": [str(user.id) for user in message.mentions],
        "mention_roles": [str(role.id) for role in message.role_mentions],
        "mention_channels": [str(channel.id) for channel in message.channel_mentions],
        "attachments": attachments,
        "embeds": embeds,
        "components": components,
        "reference": reference_info,
        "pinned": message.pinned,
        "flags": message.flags.value if message.flags else 0,
        "sender": {
            "user_id": str(message.author.id),
            "nickname": message.author.display_name,
            "card": message.author.name,
            "bot": message.author.bot,
            "system": message.author.system,
            "avatar_url": str(message.author.avatar.url) if message.author.avatar else None,
            "discriminator": message.author.discriminator,
            "color": message.author.color.value if message.author.color else None,
            "roles": [str(role.id) for role in message.author.roles] if hasattr(message.author, 'roles') else []
        },
        "channel": {
            "id": str(message.channel.id),
            "name": message.channel.name if hasattr(message.channel, 'name') else None,
            "type": str(message.channel.type),
            "category_id": str(message.channel.category_id) if hasattr(message.channel, 'category_id') else None,
            "position": message.channel.position if hasattr(message.channel, 'position') else None,
            "nsfw": message.channel.nsfw if hasattr(message.channel, 'nsfw') else None,
            "topic": message.channel.topic if hasattr(message.channel, 'topic') else None,
            "slowmode_delay": message.channel.slowmode_delay if hasattr(message.channel, 'slowmode_delay') else None
        } if isinstance(message.channel, discord.TextChannel) else {
            "id": str(message.channel.id),
            "type": str(message.channel.type)
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
