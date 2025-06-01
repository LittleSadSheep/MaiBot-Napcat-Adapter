# MaiBot-Discord-Adapter

哇！这是一个超级可爱的MaiBot Discord适配器喔！(｡･ω･｡)

## 项目介绍 喵~

这个项目是从 [MaiBot-Napcat-Adapter](https://github.com/MaiM-with-u/MaiBot-Napcat-Adapter) fork过来的捏！因为本喵想要让MaiBot能在Discord上玩耍，所以就把它魔改成了一个Discord适配器啦！(≧▽≦)

## 主要功能 喵~

- 支持Discord群聊和私聊消息的收发喔！让聊天更有趣捏~
- 支持发送文本、图片、表情包等多种消息类型捏！想发什么都可以喵！
- 支持消息回复功能，让对话更有趣喵！再也不怕找不到上下文啦！
- 支持黑白名单功能，可以控制哪些频道和用户可以和机器人玩耍喔！保护你的小天地！
- 支持语音消息（需要配置TTS）捏！让机器人也能说话喵！

## 开发状态 喵~

喵呜~这个项目还在开发中喔！(｡•́︿•̀｡)
- 可能会有亿些小bug，希望大家能帮忙找出来捏~
- 欢迎各位大佬来提交issue和pr，让这个项目变得更好喵！
- 如果你有任何想法或建议，也欢迎来讨论喔！

## 使用方法 喵~

1. 首先要在Discord开发者平台创建一个机器人喔！[点击这里](https://discord.com/developers/applications)去创建捏~
2. 复制机器人的Token，填写到`config.toml`文件里喵！
3. 创建venv并安装依赖包：
```bash
python3 -m venv MaiBot/venv      # 创建虚拟环境    
source MaiBot/venv/bin/activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple --upgrade
```
4. 运行程序：
```bash
python main.py
```

## 配置文件说明 喵~

在`config.toml`文件中，你可以设置：
- Discord机器人的Token（记得要保密喔！）
- 黑白名单（控制谁可以和机器人玩耍捏~）
- 心跳间隔（让机器人保持活力喵！）
- 日志等级（方便调试和排错喔！）
- 其他功能开关（想开就开，想关就关捏~）

## 注意事项 喵~

- 记得给机器人正确的权限喔！不然它可能会生气不理你捏~
- 如果遇到问题，可以查看日志文件，看看机器人是不是在闹小脾气喵！
- 本喵会持续更新，让机器人变得更可爱喔！

## 特别鸣谢 喵~

感谢原项目 [MaiBot-Napcat-Adapter](https://github.com/MaiM-with-u/MaiBot-Napcat-Adapter) 的开发者们！没有你们就没有这么可爱的机器人捏！

## 许可证 喵~

本项目采用 GPL-3.0 许可证喔！要遵守规则才能和机器人一起玩耍捏！

---
最后，希望这个可爱的机器人能给你带来快乐喵！(≧ω≦)