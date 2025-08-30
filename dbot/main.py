# main.py
import logging
import sys
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    InlineQueryHandler
)
from bot.handlers import MessageHandler as BotMessageHandler
from config import config

# 配置日志 - 调整httpx的日志级别
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 禁用httpx的INFO日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.ext._application").setLevel(logging.WARNING)

class SubscriptionBot:
    """机器人主类"""
    
    def __init__(self):
        if not config.BOT_TOKEN:
            logger.error("未设置BOT_TOKEN")
            sys.exit(1)
        
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        self.handler = BotMessageHandler()
        self._register_handlers()
    
    def _register_handlers(self):
        """注册所有处理器"""
        # 命令处理器
        self.application.add_handler(CommandHandler("start", self.handler.handle_start))
        self.application.add_handler(CommandHandler("help", self.handler.handle_help))
        self.application.add_handler(CommandHandler("c", self.handler.handle_clash_command))
        self.application.add_handler(CommandHandler("v", self.handler.handle_v2ray_command))
        self.application.add_handler(CommandHandler("sub", self.handler.handle_sub_command))
        self.application.add_handler(CommandHandler("sc", self.handler.handle_scan_content))
        self.application.add_handler(CommandHandler("short", self.handler.handle_short_link))
        self.application.add_handler(CommandHandler("settings", self.handler.handle_settings))
        self.application.add_handler(CommandHandler("stats", self.handler.handle_admin_stats))
        self.application.add_handler(CommandHandler("export", self.handler.handle_admin_export))
        
        # 内联查询处理器
        self.application.add_handler(InlineQueryHandler(self.handler.handle_inline_query))
        
        # 回调查询处理器
        self.application.add_handler(CallbackQueryHandler(self.handler.handle_callback_query))
        
        # 文本消息处理器
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handler.handle_text_message)
        )
        
        # 错误处理器
        self.application.add_error_handler(self._error_handler)
    
    async def _error_handler(self, update: object, context):
        """全局错误处理器"""
        logger.error(msg="Exception:", exc_info=context.error)
        
        try:
            if isinstance(update, Update) and update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ 处理请求时发生错误，请稍后重试"
                )
        except:
            pass
    
    def run(self):
        """启动机器人"""
        logger.info("机器人启动中...")
        logger.info(f"Bot Token: {config.BOT_TOKEN[:10]}...")
        self.application.run_polling(drop_pending_updates=True)
        logger.info("机器人已停止")

def main():
    """主函数"""
    try:
        bot = SubscriptionBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()