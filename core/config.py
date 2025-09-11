"""
配置管理模块 - 统一管理所有配置项
遵循单一职责原则(SRP)
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum

class ModelType(Enum):
    """AI模型类型"""
    GEMINI = "gemini"
    QW = "qw"
    GPT4 = "gpt-4"

class BotType(Enum):
    """机器人类型"""
    AI = "ai"
    SUBSCRIPTION = "subscription" 
    SNELL = "snell"

to
@dataclass
class BotConfig:
    """统一配置类"""
    # 基础配置
    TELEGRAM_TOKEN: str = ""
    DEBUG: bool = False
    
    # AI配置
    CHATPUB_API_URL: str = ""
    CHATPUB_API_KEY: str = ""
    AVAILABLE_MODELS: Dict[str, str] = field(default_factory=dict)
    DEFAULT_MODEL: ModelType = ModelType.GEMINI
    
    # 订阅配置
    SUB_API_URL: str = ""
    SUB_API_KEY: str = ""
    
    # Snell配置
    SNELL_API_URL: str = ""
    GET_NAMES_URL: str = ""
    DELETE_URL: str = ""
    
    # 消息配置
    MSG_LENGTH_LIMIT: int = 4096
    CHAT_TIMEOUT: int = 3600  # 1小时
    API_TIMEOUT: int = 120

    def __post_init__(self):
        """初始化默认值"""
        if not self.AVAILABLE_MODELS:
            self.AVAILABLE_MODELS = {
                ModelType.GEMINI.value: "gemini-2.5-flash",
                ModelType.QW.value: "qwen/qwen3-30b-a3b:free",
                ModelType.GPT4.value: "gpt-4"
            }
