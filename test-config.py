#!/usr/bin/env python3
"""
配置验证测试脚本
演示配置检查的效果
"""
import sys
import os
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("\n" + "="*60)
print("配置验证测试")
print("="*60 + "\n")

# 测试 1: 配置文件不存在
print("📋 测试 1: 配置文件不存在")
print("-" * 60)
if not os.path.exists('.env'):
    print("❌ .env 文件不存在")
    print("   运行: cp .env.example .env")
else:
    print("✅ .env 文件存在")

print()

# 测试 2: 尝试加载配置
print("📋 测试 2: 加载配置")
print("-" * 60)
try:
    from core.config import settings
    print("✅ 配置加载成功")
    print(f"   Bot Token: {settings.tg_bot_token[:10]}...")
    print(f"   Admin UID: {settings.tg_admin_uid}")
    print(f"   NodeSeek UID: {settings.nodeseek_admin_uid}")
except ValueError as e:
    print(f"❌ 配置验证失败:")
    print(f"   {e}")
except Exception as e:
    print(f"❌ 配置加载失败:")
    print(f"   {e}")

print("\n" + "="*60)
