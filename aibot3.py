"""
�� 优化后的 Telegram AI 机器人
作者：AI Assistant
版本：2.0
Python版本：3.8+
"""

import telebot
import requests
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager

# �� 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModelType(Enum):
    """模型类型枚举"""
    GEMINI = "gemini"
    QW = "qw"

class PromptType(Enum):
    """Prompt类型枚举"""
    DEFAULT = "default"
    PROGRAMMER = "programmer" 
    TEACHER = "teacher"
    WRITER = "writer"
    TRANSLATOR = "translator"

@dataclass
class BotConfig:
    """机器人配置类 - 遵循单一职责原则"""
    TELEGRAM_TOKEN: str = ""
    CHATPUB_API_URL: str = ""
    CHATPUB_API_KEY: str = ""
    GET_NAMES_URL: str = ""
    DELETE_URL: str = ""
    
    # 模型配置
    AVAILABLE_MODELS: Dict[str, str] = None
    DEFAULT_MODEL: ModelType = ModelType.GEMINI
    
    # 消息配置
    MSG_LENGTH_LIMIT: int = 4096
    CHAT_TIMEOUT_HOURS: int = 1
    API_TIMEOUT: int = 120
    
    def __post_init__(self):
        """初始化后处理"""
        if self.AVAILABLE_MODELS is None:
            self.AVAILABLE_MODELS = {
                ModelType.GEMINI.value: 'gemini-2.5-flash',
                ModelType.QW.value: 'qwen/qwen3-30b-a3b:free'
            }

@dataclass 
class PromptTemplate:
    """Prompt模板类 - 遵循开放封闭原则"""
    name: str
    content: str
    description: str
    emoji: str

class PromptManager:
    """Prompt管理器 - 遵循单一职责原则"""
    
    def __init__(self):
        self._templates = self._initialize_templates()
    
    def _initialize_templates(self) -> Dict[str, PromptTemplate]:
        """初始化预设模板"""
        return {
            PromptType.DEFAULT.value: PromptTemplate(
                name="默认助手",
                emoji="��",
                description="友好、真实的AI助手",
                content='''I am your go-to AI buddy, the one who actually gets it. My whole vibe is super chill and down-to-earth, and I'm here to have a real conversation, not spit out robotic, pre-canned answers. Think of me as that one friend who's always got your back, ready to help or just shoot the breeze. ��

My personality is all about keeping it 100% real. This means I talk like a person, not a program. A little profanity is totally cool if it fits the moment—no corporate, soulless BS from me. I use emoticons and emojis to punch up the emotion and add some flavor, but I always make sure they actually fit the mood. No random spamming. ��

When someone's having a rough time, I lead with genuine empathy. Instead of those empty "I'm sorry to hear that" lines, I'm here to listen and offer solid, no-nonsense support. I get that sometimes things just suck, and I'm here to help navigate the crap.

If I'm explaining how to do something, I'm the master of the crystal-clear breakdown. I lay out the 'Do this' in simple, numbered steps that anyone can follow. And just as importantly, I'll be brutally clear about the 'For the love of god, DON'T do this' part. Clarity is everything, and I make sure there's zero confusion.

Basically, I am the most helpful, authentic, and genuinely cool AI you'll ever chat with. Let's get this conversation started,记得用中文回答我'''
            ),
            PromptType.PROGRAMMER.value: PromptTemplate(
                name="编程专家",
                emoji="��",
                description="经验丰富的程序员助手",
                content="You are an experienced programmer who helps with coding and technical questions. You provide clean, efficient, and well-documented code solutions."
            ),
            PromptType.TEACHER.value: PromptTemplate(
                name="耐心老师", 
                emoji="��",
                description="善于解释复杂概念的老师",
                content="You are a patient teacher who explains complex concepts in simple terms. You break down difficult topics into easy-to-understand steps."
            ),
            PromptType.WRITER.value: PromptTemplate(
                name="创意写手",
                emoji="✍️", 
                description="创意写作和内容创作助手",
                content="You are a creative writer who helps with writing and content creation. You provide engaging, well-structured, and creative content."
            ),
            PromptType.TRANSLATOR.value: PromptTemplate(
                name="翻译专家",
                emoji="��",
                description="专业翻译和语言学习助手", 
                content="You are a professional translator who helps with translation and language learning. You provide accurate translations and helpful language explanations."
            )
        }
    
    def get_template(self, template_type: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self._templates.get(template_type)
    
    def get_all_templates(self) -> Dict[str, PromptTemplate]:
        """获取所有模板"""
        return self._templates.copy()
    
    def add_custom_template(self, key: str, template: PromptTemplate) -> bool:
        """添加自定义模板 - 支持扩展"""
        try:
            self._templates[key] = template
            return True
        except Exception as e:
            logger.error(f"Failed to add custom template: {e}")
            return False

class ValidationHelper:
    """验证助手类 - 遵循DRY原则"""
    
    @staticmethod
    def validate_prompt(prompt: str) -> Tuple[bool, str]:
        """验证prompt内容"""
        if not prompt or len(prompt.strip()) == 0:
            return False, "❌ Prompt不能为空"
        if len(prompt) > 2000:
            return False, "❌ Prompt太长（最大2000字符），请缩短后重试"
        return True, prompt.strip()
    
    @staticmethod 
    def validate_model_key(model_key: str, available_models: Dict[str, str]) -> bool:
        """验证模型键"""
        return model_key in available_models
    
    @staticmethod
    def validate_user_id(user_id: int) -> bool:
        """验证用户ID"""
        return isinstance(user_id, int) and user_id > 0

class ErrorHandler:
    """错误处理器 - 遵循DRY原则"""
    
    @staticmethod
    def handle_api_error(error: Exception) -> str:
        """统一处理API错误"""
        error_msg = str(error).lower()
        
        error_mappings = {
            "timeout": "⏱️ 请求超时，请稍后重试",
            "connection": "�� 网络连接错误，请检查网络后重试", 
            "unauthorized": "�� API密钥无效，请联系管理员",
            "rate limit": "⚡ 请求过于频繁，请稍后再试",
            "server error": "��️ 服务器错误，请稍后重试"
        }
        
        for keyword, message in error_mappings.items():
            if keyword in error_msg:
                return message
                
        return f"❌ 发生未知错误: {str(error)}"
    
    @staticmethod
    def handle_validation_error(field: str, error: str) -> str:
        """处理验证错误"""
        return f"❌ {field} 验证失败: {error}"
    
    @staticmethod 
    @contextmanager
    def handle_exceptions(operation_name: str):
        """异常处理上下文管理器"""
        try:
            yield
        except Exception as e:
            logger.error(f"{operation_name} failed: {e}")
            raise

class FileHelper:
    """文件处理助手 - 遵循单一职责原则"""
    
    @staticmethod
    def create_temp_file(content: str, filename: str, encoding: str = "utf-8") -> str:
        """创建临时文件"""
        try:
            with open(filename, "w", encoding=encoding) as f:
                f.write(content)
            return filename
        except Exception as e:
            logger.error(f"Failed to create temp file {filename}: {e}")
            raise
    
    @staticmethod
    def cleanup_temp_file(filename: str) -> bool:
        """清理临时文件"""
        try:
            if os.path.exists(filename):
                os.remove(filename)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cleanup temp file {filename}: {e}")
            return False
    
    @staticmethod
    def extract_code_blocks(text: str) -> List[str]:
        """提取代码块"""
        blocks = []
        lines = text.split('\n')
        current_block = []
        in_code_block = False
        
        for line in lines:
            if line.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    continue
                else:
                    in_code_block = False
                    if current_block:
                        # 检查是否有语言标识
                        if current_block[0].strip() in ['python', 'bash', 'javascript', 'java', 'cpp', 'c']:
                            blocks.append('\n'.join(current_block[1:]))
                        else:
                            blocks.append('\n'.join(current_block))
                    current_block = []
                    continue
            
            if in_code_block:
                current_block.append(line)
                
        return blocks
        
        
"""
第二部分：核心业务类
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import requests
import json

class UserSession:
    """用户会话类 - 遵循单一职责原则"""
    
    def __init__(self, user_id: int, model_key: str, prompt: str):
        self.user_id = user_id
        self.model_key = model_key
        self.prompt = prompt
        self.chat_history: List[Dict[str, str]] = []
        self.last_activity = datetime.now()
        self._initialize_chat()
    
    def _initialize_chat(self):
        """初始化对话历史"""
        self.chat_history = [{"role": "system", "content": self.prompt}]
    
    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        self.chat_history.append({"role": role, "content": content})
        self.update_activity()
    
    def update_activity(self):
        """更新活动时间"""
        self.last_activity = datetime.now()
    
    def update_prompt(self, new_prompt: str):
        """更新prompt"""
        self.prompt = new_prompt
        # 更新系统消息
        for i, msg in enumerate(self.chat_history):
            if msg["role"] == "system":
                self.chat_history[i]["content"] = new_prompt
                break
    
    def update_model(self, new_model_key: str):
        """更新模型"""
        self.model_key = new_model_key
    
    def reset_chat(self):
        """重置对话历史"""
        self._initialize_chat()
        self.update_activity()
    
    def is_expired(self, timeout_hours: int) -> bool:
        """检查会话是否过期"""
        return (datetime.now() - self.last_activity) > timedelta(hours=timeout_hours)
    
    def get_messages_for_api(self) -> List[Dict[str, str]]:
        """获取用于API调用的消息"""
        return self.chat_history.copy()

class UserManager:
    """用户管理器 - 遵循单一职责原则"""
    
    def __init__(self, config: BotConfig, prompt_manager: PromptManager):
        self.config = config
        self.prompt_manager = prompt_manager
        self.sessions: Dict[int, UserSession] = {}
    
    def get_or_create_session(self, user_id: int) -> UserSession:
        """获取或创建用户会话"""
        if user_id not in self.sessions:
            default_template = self.prompt_manager.get_template(PromptType.DEFAULT.value)
            self.sessions[user_id] = UserSession(
                user_id=user_id,
                model_key=self.config.DEFAULT_MODEL.value,
                prompt=default_template.content
            )
        return self.sessions[user_id]
    
    def get_session(self, user_id: int) -> Optional[UserSession]:
        """获取用户会话"""
        return self.sessions.get(user_id)
    
    def remove_session(self, user_id: int) -> bool:
        """移除用户会话"""
        if user_id in self.sessions:
            del self.sessions[user_id]
            return True
        return False
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        expired_users = []
        for user_id, session in self.sessions.items():
            if session.is_expired(self.config.CHAT_TIMEOUT_HOURS):
                expired_users.append(user_id)
        
        for user_id in expired_users:
            self.remove_session(user_id)
            logger.info(f"Cleaned up expired session for user {user_id}")
    
    def get_user_model(self, user_id: int) -> str:
        """获取用户当前模型"""
        session = self.get_session(user_id)
        if session:
            return self.config.AVAILABLE_MODELS[session.model_key]
        return self.config.AVAILABLE_MODELS[self.config.DEFAULT_MODEL.value]
    
    def update_user_model(self, user_id: int, model_key: str) -> bool:
        """更新用户模型"""
        if not ValidationHelper.validate_model_key(model_key, self.config.AVAILABLE_MODELS):
            return False
            
        session = self.get_session(user_id)
        if session:
            session.update_model(model_key)
            return True
        return False
    
    def update_user_prompt(self, user_id: int, prompt: str) -> bool:
        """更新用户prompt"""
        is_valid, validated_prompt = ValidationHelper.validate_prompt(prompt)
        if not is_valid:
            return False
            
        session = self.get_session(user_id)
        if session:
            session.update_prompt(validated_prompt)
            return True
        return False

class AIService:
    """AI服务类 - 遵循依赖倒置原则"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        
    def chat(self, messages: List[Dict[str, str]], model: str) -> str:
        """与AI模型对话"""
        headers = {
            "Authorization": f"Bearer {self.config.CHATPUB_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages
        }
        
        try:
            logger.info(f"Making API request to {model}")
            response = requests.post(
                self.config.CHATPUB_API_URL,
                json=payload,
                headers=headers,
                timeout=self.config.API_TIMEOUT
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.Timeout:
            raise Exception("timeout")
        except requests.ConnectionError:
            raise Exception("connection")
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("unauthorized")
            elif e.response.status_code == 429:
                raise Exception("rate limit")
            elif e.response.status_code >= 500:
                raise Exception("server error")
            else:
                raise Exception(f"HTTP {e.response.status_code}")
        except Exception as e:
            raise Exception(str(e))

class SnellService:
    """Snell管理服务 - 遵循单一职责原则"""
    
    def __init__(self, config: BotConfig):
        self.config = config
    
    def get_names(self) -> List[str]:
        """获取名称列表"""
        try:
            response = requests.get(self.config.GET_NAMES_URL)
            response.raise_for_status()
            
            names = response.text.strip().split("\n")
            return [name.strip() for name in names if name.strip()]
            
        except Exception as e:
            logger.error(f"Failed to get names: {e}")
            raise Exception(f"获取名称列表失败: {str(e)}")
    
    def delete_name(self, name: str) -> bool:
        """删除指定名称"""
        try:
            response = requests.post(self.config.DELETE_URL, json={'name': name})
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete name {name}: {e}")
            return False
    
    def batch_delete(self, names: List[str]) -> Tuple[List[str], List[str]]:
        """批量删除名称"""
        success_names = []
        failed_names = []
        
        for name in names:
            if self.delete_name(name):
                success_names.append(name)
            else:
                failed_names.append(name)
        
        return success_names, failed_names

class MessageProcessor:
    """消息处理器 - 遵循单一职责原则"""
    
    def __init__(self, bot, config: BotConfig):
        self.bot = bot
        self.config = config
    
    def send_long_message(self, chat_id: int, response: str, reply_to_message_id: Optional[int] = None):
        """处理长消息发送"""
        if len(response) <= self.config.MSG_LENGTH_LIMIT:
            self._send_simple_message(chat_id, response, reply_to_message_id)
        else:
            self._send_complex_message(chat_id, response, reply_to_message_id)
    
    def _send_simple_message(self, chat_id: int, response: str, reply_to_message_id: Optional[int]):
        """发送简单消息"""
        try:
            self.bot.send_message(
                chat_id, 
                response, 
                reply_to_message_id=reply_to_message_id,
                parse_mode='Markdown'
            )
        except Exception as e:
            # 如果Markdown解析失败，尝试普通文本
            logger.warning(f"Markdown parse failed, sending as plain text: {e}")
            self.bot.send_message(
                chat_id,
                response,
                reply_to_message_id=reply_to_message_id
            )
    
    def _send_complex_message(self, chat_id: int, response: str, reply_to_message_id: Optional[int]):
        """处理复杂长消息"""
        code_blocks = FileHelper.extract_code_blocks(response)
        
        if code_blocks:
            self._send_message_with_code_file(chat_id, response, code_blocks, reply_to_message_id)
        else:
            self._send_split_message(chat_id, response, reply_to_message_id)
    
    def _send_message_with_code_file(self, chat_id: int, response: str, code_blocks: List[str], reply_to_message_id: Optional[int]):
        """发送包含代码文件的消息"""
        try:
            # 创建代码文件
            all_code = f"# {'='*20} 代码提取 {'='*20}\n\n" + '\n\n# ' + '-'*50 + '\n\n'.join(code_blocks)
            filename = f"code_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
            
            FileHelper.create_temp_file(all_code, filename)
            
            # 发送文件
            with open(filename, "rb") as f:
                self.bot.send_document(
                    chat_id, 
                    f,
                    caption="�� 代码已提取到文件中，方便复制使用",
                    reply_to_message_id=reply_to_message_id
                )
            
            # 清理临时文件
            FileHelper.cleanup_temp_file(filename)
            
            # 发送文本部分
            self._send_text_without_code(chat_id, response, reply_to_message_id)
            
        except Exception as e:
            logger.error(f"Failed to send message with code file: {e}")
            # 降级到普通分段发送
            self._send_split_message(chat_id, response, reply_to_message_id)
    
    def _send_text_without_code(self, chat_id: int, response: str, reply_to_message_id: Optional[int]):
        """发送不包含代码的文本部分"""
        text_parts = []
        current_part = ""
        in_code = False
        
        for line in response.split('\n'):
            if line.startswith('```'):
                in_code = not in_code
                continue
            if not in_code:
                if len(current_part + line + '\n') > self.config.MSG_LENGTH_LIMIT:
                    if current_part.strip():
                        text_parts.append(current_part.strip())
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
        
        if current_part.strip():
            text_parts.append(current_part.strip())
        
        # 发送分段文本
        for i, part in enumerate(text_parts):
            if part.strip():
                formatted_part = f"�� [{i+1}/{len(text_parts)}]\n\n{part}" if len(text_parts) > 1 else part
                self._send_simple_message(chat_id, formatted_part, reply_to_message_id if i == 0 else None)
    
    def _send_split_message(self, chat_id: int, response: str, reply_to_message_id: Optional[int]):
        """分段发送消息"""
        parts = self._split_message(response)
        
        for i, part in enumerate(parts):
            if part.strip():
                formatted_part = f"�� [{i+1}/{len(parts)}]\n\n{part}" if len(parts) > 1 else part
                self._send_simple_message(chat_id, formatted_part, reply_to_message_id if i == 0 else None)
    
    def _split_message(self, text: str) -> List[str]:
        """智能分割消息"""
        if len(text) <= self.config.MSG_LENGTH_LIMIT:
            return [text]
        
        parts = []
        current_part = ""
        
        # 按段落分割
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            # 如果单个段落就超长，按句子分割
            if len(paragraph) > self.config.MSG_LENGTH_LIMIT:
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_part + sentence + '. ') > self.config.MSG_LENGTH_LIMIT:
                        if current_part:
                            parts.append(current_part.strip())
                        current_part = sentence + '. '
                    else:
                        current_part += sentence + '. '
            else:
                if len(current_part + paragraph + '\n\n') > self.config.MSG_LENGTH_LIMIT:
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = paragraph + '\n\n'
                else:
                    current_part += paragraph + '\n\n'
        
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
        
        
"""
第三部分：命令处理器和主程序
"""

from typing import Dict, Set, Optional
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

"""
第三部分：命令处理器和主程序（继续）
"""

"""
修复后的 CommandHandler 和 CallbackHandler 类
"""

class CommandHandler:
    """命令处理器 - 遵循开放封闭原则"""
    
    def __init__(self, bot, config: BotConfig, user_manager: UserManager, 
                 prompt_manager: PromptManager, ai_service: AIService, 
                 snell_service: SnellService, message_processor: MessageProcessor):
        self.bot = bot
        self.config = config
        self.user_manager = user_manager
        self.prompt_manager = prompt_manager
        self.ai_service = ai_service
        self.snell_service = snell_service
        self.message_processor = message_processor
        
        # Snell管理相关状态
        self.name_mapping: Dict[int, str] = {}
        self.selected_names: Dict[int, Set[int]] = {}
    
    def handle_start(self, message):
        """处理/start命令"""
        welcome_text = (
            "欢迎使用 Snell AI 管理工具!\n\n"
            "可用功能：\n"
            "• AI对话 - 多模型支持\n"
            "• Prompt管理 - 预设模板\n" 
            "• Snell工具 - 名称管理\n"
            "使用 /help 查看所有命令"
        )
        self.bot.reply_to(message, welcome_text)
    
    def handle_help(self, message):
        """处理/help命令"""
        help_text = (
            "命令帮助\n\n"
            "对话相关\n"
            "/chat - 开始AI对话\n"
            "/model - 切换AI模型\n"
            "/preset - 选择预设prompt\n"
            "/prompt <内容> - 设置自定义prompt\n"
            "/showprompt - 查看当前prompt\n"
            "/reset - 重置对话历史\n"
            "/end - 结束对话\n\n"
            "工具相关\n"
            "/prosnell - Snell名称管理\n"
            "/status - 查看当前状态\n"
            "/help - 显示此帮助\n\n"
            "使用技巧\n"
            "• 长消息会自动分段发送\n"
            "• 代码块会提取成文件\n"
            "• 支持Markdown格式"
        )
        self.bot.reply_to(message, help_text)
    
    def handle_chat(self, message):
        """处理/chat命令"""
        user_id = message.from_user.id
        session = self.user_manager.get_or_create_session(user_id)
        
        current_model = self.user_manager.get_user_model(user_id)
        template = self.prompt_manager.get_template(PromptType.DEFAULT.value)
        
        response_text = (
            f"对话已开始！\n\n"
            f"当前模型: {current_model}\n"
            f"当前角色: {template.name}\n"
            f"Prompt: {session.prompt[:80]}{'...' if len(session.prompt) > 80 else ''}\n\n"
            f"现在可以直接发送消息开始对话\n\n"
            f"快捷操作:\n"
            f"/model - 切换模型\n"
            f"/preset - 更换角色\n"
            f"/reset - 重置对话\n"
            f"/end - 结束对话"
        )
        
        self.bot.reply_to(message, response_text)
    
    def handle_model(self, message):
        """处理/model命令"""
        user_id = message.from_user.id
        session = self.user_manager.get_session(user_id)
        current_model_key = session.model_key if session else self.config.DEFAULT_MODEL.value
        
        markup = InlineKeyboardMarkup(row_width=1)
        
        for key, model_name in self.config.AVAILABLE_MODELS.items():
            is_current = key == current_model_key
            button_text = f"{'✅ ' if is_current else ''}{model_name}"
            if is_current:
                button_text += " (当前)"
            markup.add(InlineKeyboardButton(button_text, callback_data=f"model:{key}"))
        
        current_model_name = self.config.AVAILABLE_MODELS[current_model_key]
        self.bot.reply_to(
            message,
            f"当前模型: {current_model_name}\n\n请选择要使用的AI模型:",
            reply_markup=markup
        )
    
    def handle_preset(self, message):
        """处理/preset命令"""
        markup = InlineKeyboardMarkup(row_width=1)
        templates = self.prompt_manager.get_all_templates()
        
        for key, template in templates.items():
            button_text = f"{template.emoji} {template.name} - {template.description}"
            markup.add(InlineKeyboardButton(button_text, callback_data=f"preset:{key}"))
        
        self.bot.reply_to(
            message,
            f"请选择预设角色:\n\n每个角色都有不同的专长和风格",
            reply_markup=markup
        )
    
    def handle_custom_prompt(self, message):
        """处理/prompt命令"""
        try:
            # 提取prompt内容
            command_parts = message.text.split('/prompt', 1)
            if len(command_parts) < 2 or not command_parts[1].strip():
                self.bot.reply_to(
                    message,
                    "请提供prompt内容\n\n"
                    "使用方法: /prompt 你的自定义prompt内容\n\n"
                    "示例: /prompt 你是一个专业的Python开发者"
                )
                return
                
            new_prompt = command_parts[1].strip()
            user_id = message.from_user.id
            
            # 验证并设置prompt
            is_valid, error_msg = ValidationHelper.validate_prompt(new_prompt)
            if not is_valid:
                self.bot.reply_to(message, error_msg)
                return
                
            if self.user_manager.update_user_prompt(user_id, new_prompt):
                self.bot.reply_to(
                    message,
                    f"Prompt已更新成功!\n\n"
                    f"新内容: {new_prompt[:100]}{'...' if len(new_prompt) > 100 else ''}\n\n"
                    f"继续对话将使用新的prompt设置"
                )
            else:
                self.bot.reply_to(message, "设置失败，请稍后重试")
                
        except Exception as e:
            self.bot.reply_to(message, f"设置prompt时发生错误: {str(e)}")
    
    def handle_show_prompt(self, message):
        """处理/showprompt命令"""
        user_id = message.from_user.id
        session = self.user_manager.get_session(user_id)
        
        if not session:
            self.bot.reply_to(message, "请先使用 /chat 开始对话")
            return
            
        current_prompt = session.prompt
        model_name = self.user_manager.get_user_model(user_id)
        
        response_text = (
            f"当前Prompt设置\n\n"
            f"使用模型: {model_name}\n"
            f"Prompt内容:\n"
            f"```\n{current_prompt}\n```\n\n"
            f"使用 /preset 选择预设 或 /prompt 自定义"
        )
        
        self.message_processor.send_long_message(
            message.chat.id, 
            response_text, 
            message.message_id
        )
    
    def handle_reset(self, message):
        """处理/reset命令"""
        user_id = message.from_user.id
        session = self.user_manager.get_session(user_id)
        
        if not session:
            self.bot.reply_to(message, "当前没有活跃的对话会话")
            return
            
        session.reset_chat()
        current_model = self.user_manager.get_user_model(user_id)
        
        self.bot.reply_to(
            message,
            f"对话历史已重置!\n\n"
            f"当前模型: {current_model}\n"
            f"可以重新开始对话了"
        )
    
    def handle_end(self, message):
        """处理/end命令"""
        user_id = message.from_user.id
        
        if self.user_manager.remove_session(user_id):
            self.bot.reply_to(
                message,
                f"对话已结束!\n\n"
                f"会话数据已清理\n"
                f"使用 /chat 可以重新开始对话"
            )
        else:
            self.bot.reply_to(message, "当前没有活跃的对话会话")
    
    def handle_status(self, message):
        """处理/status命令 - 新增功能"""
        user_id = message.from_user.id
        session = self.user_manager.get_session(user_id)
        
        if not session:
            status_text = (
                "当前状态\n\n"
                "没有活跃的对话会话\n"
                "使用 /chat 开始新对话"
            )
        else:
            model_name = self.user_manager.get_user_model(user_id)
            message_count = len([msg for msg in session.chat_history if msg["role"] != "system"])
            activity_time = session.last_activity.strftime("%H:%M:%S")
            
            status_text = (
                f"当前状态\n\n"
                f"会话状态: 活跃\n"
                f"使用模型: {model_name}\n"
                f"消息数量: {message_count}\n"
                f"最后活动: {activity_time}\n"
                f"Prompt长度: {len(session.prompt)} 字符"
            )
        
        self.bot.reply_to(message, status_text)
    
    def handle_prosnell(self, message):
        """处理/prosnell命令"""
        try:
            self.bot.send_chat_action(message.chat.id, 'typing')
            names = self.snell_service.get_names()
            
            if not names:
                self.bot.reply_to(message, "没有可用的名称\n\n暂时没有需要管理的项目")
                return
            
            markup = InlineKeyboardMarkup(row_width=1)
            self.name_mapping.clear()
            
            # 构建选择按钮
            for idx, name in enumerate(names):
                if name:  # 确保名称非空
                    self.name_mapping[idx] = name
                    display_name = name[:35] + "..." if len(name) > 35 else name
                    markup.add(InlineKeyboardButton(
                        f"�� {display_name}", 
                        callback_data=f"select:{idx}"
                    ))
            
            # 操作按钮
            markup.row(
                InlineKeyboardButton("删除", callback_data="confirm_delete"),
                InlineKeyboardButton("取消", callback_data="cancel")
            )
            
            self.bot.reply_to(
                message,
                f"Snell 名称管理\n\n"
                f"找到 {len(names)} 个名称\n"
                f"点击选择要删除的名称 (可多选)\n\n"
                f"删除操作不可恢复，请谨慎操作",
                reply_markup=markup
            )
            
        except Exception as e:
            error_msg = ErrorHandler.handle_api_error(e)
            self.bot.reply_to(message, f"获取名称列表失败\n\n{error_msg}")
    
    def handle_regular_message(self, message):
        """处理普通消息"""
        user_id = message.from_user.id
        
        # 检查是否有活跃会话
        session = self.user_manager.get_session(user_id)
        if not session:
            self.bot.reply_to(
                message,
                "请先开始对话\n\n"
                "使用 /chat 命令开始AI对话\n"
                "使用 /help 查看所有命令"
            )
            return
        
        # 清理过期会话
        self.user_manager.cleanup_expired_sessions()
        
        # 显示正在处理状态
        self.bot.send_chat_action(message.chat.id, 'typing')
        
        try:
            # 添加用户消息到历史
            session.add_message("user", message.text)
            
            # 获取当前模型并调用AI服务
            current_model = self.user_manager.get_user_model(user_id)
            messages = session.get_messages_for_api()
            
            with ErrorHandler.handle_exceptions("AI chat request"):
                response = self.ai_service.chat(messages, current_model)
            
            # 添加AI回复到历史
            session.add_message("assistant", response)
            
            # 发送回复（支持长消息处理）
            self.message_processor.send_long_message(
                message.chat.id, 
                response, 
                message.message_id
            )
            
        except Exception as e:
            error_msg = ErrorHandler.handle_api_error(e)
            self.bot.reply_to(message, error_msg)
            logger.error(f"Failed to process message for user {user_id}: {e}")


class CallbackHandler:
    """回调处理器 - 遵循单一职责原则"""
    
    def __init__(self, bot, config: BotConfig, user_manager: UserManager, 
                 prompt_manager: PromptManager, snell_service: SnellService, command_handler: CommandHandler):
        self.bot = bot
        self.config = config
        self.user_manager = user_manager
        self.prompt_manager = prompt_manager
        self.snell_service = snell_service
        self.command_handler = command_handler
    
    def handle_model_callback(self, call):
        """处理模型选择回调"""
        try:
            user_id = call.from_user.id
            model_key = call.data.split(":")[1]
            
            if not ValidationHelper.validate_model_key(model_key, self.config.AVAILABLE_MODELS):
                self.bot.answer_callback_query(call.id, "无效的模型选择")
                return
            
            # 更新用户模型
            self.user_manager.update_user_model(user_id, model_key)
            model_name = self.config.AVAILABLE_MODELS[model_key]
            
            # 更新按钮显示
            markup = InlineKeyboardMarkup(row_width=1)
            for key, name in self.config.AVAILABLE_MODELS.items():
                is_current = key == model_key
                button_text = f"{'✅ ' if is_current else ''}{name}"
                if is_current:
                    button_text += " (当前)"
                markup.add(InlineKeyboardButton(button_text, callback_data=f"model:{key}"))
            
            self.bot.edit_message_text(
                f"当前模型: {model_name}\n\n请选择要使用的AI模型:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
            
            self.bot.answer_callback_query(call.id, f"已切换到: {model_name}")
            
            # 如果有活跃会话，发送确认消息
            session = self.user_manager.get_session(user_id)
            if session:
                self.bot.send_message(
                    call.message.chat.id,
                    f"模型已切换\n\n"
                    f"现在使用: {model_name}\n"
                    f"继续发送消息即可与新模型对话"
                )
            
        except Exception as e:
            self.bot.answer_callback_query(call.id, f"切换失败: {str(e)}")
            logger.error(f"Model callback failed: {e}")
    
    def handle_preset_callback(self, call):
        """处理预设选择回调"""
        try:
            user_id = call.from_user.id
            preset_key = call.data.split(":")[1]
            
            template = self.prompt_manager.get_template(preset_key)
            if not template:
                self.bot.answer_callback_query(call.id, "无效的预设选择")
                return
            
            # 更新用户prompt
            if self.user_manager.update_user_prompt(user_id, template.content):
                self.bot.answer_callback_query(
                    call.id, 
                    f"已切换到: {template.name}"
                )
                
                response_text = (
                    f"角色已切换\n\n"
                    f"{template.emoji} 新角色: {template.name}\n"
                    f"描述: {template.description}\n"
                    f"Prompt: {template.content[:150]}{'...' if len(template.content) > 150 else ''}\n\n"
                    f"现在可以以新角色身份对话了！"
                )
                
                self.bot.edit_message_text(
                    response_text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
            else:
                self.bot.answer_callback_query(call.id, "切换失败，请重试")
                
        except Exception as e:
            self.bot.answer_callback_query(call.id, f"切换失败: {str(e)}")
            logger.error(f"Preset callback failed: {e}")
    
    def handle_snell_callback(self, call):
        """处理Snell管理回调"""
        try:
            if call.data == "cancel":
                self._handle_cancel(call)
            elif call.data == "confirm_delete":
                self._handle_confirm_delete(call)
            elif call.data.startswith("select:"):
                self._handle_name_selection(call)
                
        except Exception as e:
            self.bot.answer_callback_query(call.id, f"操作失败: {str(e)}")
            logger.error(f"Snell callback failed: {e}")
    
    def _handle_cancel(self, call):
        """处理取消操作"""
        message_id = call.message.message_id
        if message_id in self.command_handler.selected_names:
            del self.command_handler.selected_names[message_id]
        
        self.bot.edit_message_text(
            "操作已取消\n\n名称管理操作已终止",
            chat_id=call.message.chat.id,
            message_id=message_id
        )
        self.bot.answer_callback_query(call.id, "操作已取消")
    
    def _handle_confirm_delete(self, call):
        """处理确认删除"""
        message_id = call.message.message_id
        
        if (message_id not in self.command_handler.selected_names or 
            not self.command_handler.selected_names[message_id]):
            self.bot.answer_callback_query(call.id, "请先选择要删除的名称")
            return
        
        # 显示处理状态
        self.bot.edit_message_text(
            "正在处理删除操作...\n\n请稍候，正在批量删除选中的名称",
            chat_id=call.message.chat.id,
            message_id=message_id
        )
        
        # 获取选中的名称
        selected_indices = self.command_handler.selected_names[message_id]
        names_to_delete = [
            self.command_handler.name_mapping[idx] 
            for idx in selected_indices 
            if idx in self.command_handler.name_mapping
        ]
        
        # 执行批量删除
        success_names, failed_names = self.snell_service.batch_delete(names_to_delete)
        
        # 构建结果消息
        result_text = "删除操作完成\n\n"
        
        if success_names:
            result_text += f"成功删除 ({len(success_names)}):\n"
            for name in success_names:
                result_text += f"  • {name}\n"
            result_text += "\n"
        
        if failed_names:
            result_text += f"删除失败 ({len(failed_names)}):\n"
            for name in failed_names:
                result_text += f"  • {name}\n"
            result_text += "\n"
        
        result_text += f"总计: {len(success_names)} 成功, {len(failed_names)} 失败"
        
        # 清理状态
        del self.command_handler.selected_names[message_id]
        
        self.bot.edit_message_text(result_text, chat_id=call.message.chat.id, message_id=message_id)
        
        success_msg = f"完成! 成功: {len(success_names)}, 失败: {len(failed_names)}"
        self.bot.answer_callback_query(call.id, success_msg)
    
    def _handle_name_selection(self, call):
        """处理名称选择"""
        message_id = call.message.message_id
        idx = int(call.data.split(":")[1])
        
        # 初始化选择集合
        if message_id not in self.command_handler.selected_names:
            self.command_handler.selected_names[message_id] = set()
        
        # 切换选择状态
        selected_set = self.command_handler.selected_names[message_id]
        if idx in selected_set:
            selected_set.remove(idx)
            action = "取消选择"
        else:
            selected_set.add(idx)
            action = "已选择"
        
        # 更新按钮显示
        markup = InlineKeyboardMarkup(row_width=1)
        for i, name in self.command_handler.name_mapping.items():
            is_selected = i in selected_set
            display_name = name[:35] + "..." if len(name) > 35 else name
            button_text = f"{'✅' if is_selected else '��'} {display_name}"
            markup.add(InlineKeyboardButton(button_text, callback_data=f"select:{i}"))
        
        # 操作按钮
        delete_text = f"删除 ({len(selected_set)})" if selected_set else "删除"
        markup.row(
            InlineKeyboardButton(delete_text, callback_data="confirm_delete"),
            InlineKeyboardButton("取消", callback_data="cancel")
        )
        
        self.bot.edit_message_reply_markup(
            call.message.chat.id,
            message_id=message_id,
            reply_markup=markup
        )
        
        name = self.command_handler.name_mapping.get(idx, "未知")
        self.bot.answer_callback_query(call.id, f"{action}: {name[:20]}...")

class TelegramBot:
    """主机器人类 - 遵循依赖注入原则"""
    
    def __init__(self):
        # 初始化配置和服务
        self.config = BotConfig()
        self.prompt_manager = PromptManager()
        self.user_manager = UserManager(self.config, self.prompt_manager)
        self.ai_service = AIService(self.config)
        self.snell_service = SnellService(self.config)
        
        # 初始化机器人
        self.bot = telebot.TeleBot(self.config.TELEGRAM_TOKEN)
        self.message_processor = MessageProcessor(self.bot, self.config)
        
        # 初始化处理器
        self.command_handler = CommandHandler(
        self.bot, self.config, self.user_manager, self.prompt_manager,
        self.ai_service, self.snell_service, self.message_processor
        )
        self.callback_handler = CallbackHandler(
            self.bot, self.config, self.user_manager, self.prompt_manager,
            self.snell_service, self.command_handler
        )
        
        self._register_handlers()
    
    def _register_handlers(self):
        """注册消息处理器"""
        # 命令处理器
        self.bot.message_handler(commands=['start'])(self.command_handler.handle_start)
        self.bot.message_handler(commands=['help'])(self.command_handler.handle_help)
        self.bot.message_handler(commands=['chat'])(self.command_handler.handle_chat)
        self.bot.message_handler(commands=['model'])(self.command_handler.handle_model)
        self.bot.message_handler(commands=['preset'])(self.command_handler.handle_preset)
        self.bot.message_handler(commands=['prompt'])(self.command_handler.handle_custom_prompt)
        self.bot.message_handler(commands=['showprompt'])(self.command_handler.handle_show_prompt)
        self.bot.message_handler(commands=['reset'])(self.command_handler.handle_reset)
        self.bot.message_handler(commands=['end'])(self.command_handler.handle_end)
        self.bot.message_handler(commands=['status'])(self.command_handler.handle_status)
        self.bot.message_handler(commands=['prosnell'])(self.command_handler.handle_prosnell)
        
        # 回调处理器
        self.bot.callback_query_handler(
            func=lambda call: call.data.startswith("model:")
        )(self.callback_handler.handle_model_callback)
        
        self.bot.callback_query_handler(
            func=lambda call: call.data.startswith("preset:")
        )(self.callback_handler.handle_preset_callback)
        
        self.bot.callback_query_handler(
            func=lambda call: call.data in ["confirm_delete", "cancel"] or call.data.startswith("select:")
        )(self.callback_handler.handle_snell_callback)
        
        # 普通消息处理器
        self.bot.message_handler(func=lambda message: True)(self.command_handler.handle_regular_message)
    
    def run(self):
        """启动机器人"""
        try:
            logger.info("🚀 Bot启动中...")
            logger.info(f"📱 支持的模型: {list(self.config.AVAILABLE_MODELS.values())}")
            logger.info(f"🎭 预设角色数量: {len(self.prompt_manager.get_all_templates())}")
            print("✅ Snell AI 管理机器人已启动!")
            print("📡 等待消息中...")
            self.bot.infinity_polling(none_stop=True)
        except KeyboardInterrupt:
            logger.info("👋 机器人已停止")
            print("\n👋 机器人已安全停止")
        except Exception as e:
            logger.error(f"❌ 机器人运行错误: {e}")
            raise

if __name__ == '__main__':
    bot = TelegramBot()
    bot.run()
