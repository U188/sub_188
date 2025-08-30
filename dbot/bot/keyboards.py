# bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class KeyboardBuilder:
    """键盘构建器"""
    
    @staticmethod
    def get_main_menu() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("📊 查询订阅", callback_data="query_sub"),
                InlineKeyboardButton("⚙️ 设置", callback_data="settings")
            ],
            [
                InlineKeyboardButton("📖 使用帮助", callback_data="help"),
                InlineKeyboardButton("ℹ️ 关于", callback_data="about")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_subscription_actions(url: str) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🔄 刷新", callback_data="refresh"),
                InlineKeyboardButton("📥 下载配置", callback_data="download")
            ],
            [
                InlineKeyboardButton("📋 节点列表", callback_data="nodes"),
                InlineKeyboardButton("📤 分享", callback_data="share")
            ],
            [
                InlineKeyboardButton("📊 详细统计", callback_data="stats"),
                InlineKeyboardButton("🔗 转换格式", callback_data="convert")
            ],
            [
                InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_download_options() -> InlineKeyboardMarkup:
        """下载选项键盘"""
        keyboard = [
            [
                InlineKeyboardButton("📄 Clash配置", callback_data="dl_clash"),
                InlineKeyboardButton("📄 V2Ray配置", callback_data="dl_v2ray")
            ],
            [
                InlineKeyboardButton("📄 原始配置", callback_data="dl_raw"),
                InlineKeyboardButton("📄 Base64", callback_data="dl_base64")
            ],
            [
                InlineKeyboardButton("🔙 返回", callback_data="back")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_settings_menu() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🌐 默认UA", callback_data="set_ua"),
                InlineKeyboardButton("📊 显示设置", callback_data="set_display")
            ],
            [
                InlineKeyboardButton("🔔 通知设置", callback_data="set_notify"),
                InlineKeyboardButton("💾 缓存设置", callback_data="set_cache")
            ],
            [
                InlineKeyboardButton("🔙 返回", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_scan_actions() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("📋 节点列表", callback_data="nodes"),
                InlineKeyboardButton("📊 统计信息", callback_data="stats")
            ],
            [
                InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_short_link_actions(short_url: str) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("📋 复制链接", callback_data=f"copy:{short_url[:20]}")
            ],
            [
                InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_back_button() -> InlineKeyboardMarkup:
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="back")]]
        return InlineKeyboardMarkup(keyboard)