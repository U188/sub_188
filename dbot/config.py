# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """配置管理类 - 遵循KISS原则，简单直观"""
    # Telegram配置
    BOT_TOKEN = ""
    
    # 网络配置
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    
    # 缓存配置
    CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))  # 5分钟
    
    # 显示配置
    PROGRESS_BAR_LENGTH = 20
    MAX_NODES_DISPLAY = 50
    
    # User-Agent列表（模拟不同客户端）
    USER_AGENTS = {
        'clash': 'Clash/2023.01.01',
        'v2ray': 'v2ray/5.0.0',
        'shadowrocket': 'Shadowrocket/2.0.0'
    }

config = Config()