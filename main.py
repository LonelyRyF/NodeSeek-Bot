#!/usr/bin/env python3
"""
Telegram Bot + NodeSeek 论坛私信验证系统
使用 cloudscraper 绕过 Cloudflare 验证
"""

import os
import sys
import asyncio
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.bot import BotApp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """主入口"""
    logger.info("="*50)
    logger.info("Telegram NodeSeek 验证 Bot")
    logger.info("="*50)
    
    try:
        bot = BotApp()
        await bot.startup()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号...")
    except Exception as e:
        logger.error(f"Bot 运行出错: {e}")
        return 1
    finally:
        try:
            await bot.cleanup()
        except:
            pass
        logger.info("Bot 已停止")
    
    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
