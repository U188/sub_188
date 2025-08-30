# bot/handlers.py
import re
import logging
import hashlib
import time
import base64
import io
import yaml
import json
import urllib.parse
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from services.subscription import SubscriptionService
from services.shortlink import ShortLinkService
from utils.formatters import (
    format_bytes, format_timestamp, calculate_time_left,
    generate_progress_bar, format_nodes_list
)
from bot.keyboards import KeyboardBuilder
from config import config

logger = logging.getLogger(__name__)

# bot/handlers.py (在文件开头添加导入)
from utils.storage import SubscriptionStorage

# 在 MessageHandler 类的 __init__ 方法中添加
class MessageHandler:
    """消息处理器"""
    
    def __init__(self):
        self.subscription_service = SubscriptionService()
        self.shortlink_service = ShortLinkService()
        self.keyboard_builder = KeyboardBuilder()
        self.user_data = {}
        self.user_settings = {}
        self.storage = SubscriptionStorage()  # 添加存储管理器
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/start命令"""
        user = update.effective_user
        welcome_message = (
            f"👋 欢迎，{user.first_name}！\n\n"
            "🤖 <b>订阅查询机器人</b>\n\n"
            "📋 <b>支持的命令：</b>\n"
            "/c [链接] - 查询Clash订阅\n"
            "/v [链接] - 查询V2Ray订阅\n"
            "/sub [链接] - 通用订阅查询\n"
            "/sc [内容] - 扫描订阅内容\n"
            "/short [链接] - 生成短链接\n"
            "/settings - 用户设置\n\n"
            "💡 <b>使用技巧：</b>\n"
            "• 直接发送链接自动识别\n"
            "• 支持内联查询 @bot [链接]\n\n"
            "点击下方按钮开始使用 👇"
        )
        
        await update.message.reply_html(
            welcome_message,
            reply_markup=self.keyboard_builder.get_main_menu()
        )
    
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/help命令"""
        help_text = (
            "📖 <b>使用帮助</b>\n\n"
            "<b>基本命令：</b>\n"
            "/start - 开始使用\n"
            "/help - 显示帮助\n"
            "/c [链接] - 查询Clash订阅\n"
            "/v [链接] - 查询V2Ray订阅\n"
            "/sub [链接] - 通用查询\n"
            "/sc [内容] - 扫描内容\n"
            "/short [链接] - 短链接\n\n"
            "<b>功能说明：</b>\n"
            "• 支持多种订阅格式\n"
            "• 自动解析流量信息\n"
            "• 统计节点分布\n"
            "• 支持缓存加速\n"
            "• 支持下载配置文件\n"
        )
        
        await update.message.reply_html(help_text)
    
    async def handle_clash_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/c命令"""
        await self._handle_subscription(update, context, 'clash')
    
    async def handle_v2ray_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/v命令"""
        await self._handle_subscription(update, context, 'v2ray')
    
    async def handle_sub_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/sub命令"""
        await self._handle_subscription(update, context, 'auto')
    
    async def handle_scan_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/sc命令"""
        text = update.message.text
        content = text.replace('/sc', '').strip()
        
        if not content:
            await update.message.reply_text(
                "❌ 请提供要扫描的内容\n"
                "用法: /sc [订阅内容或Base64]"
            )
            return
        
        processing_msg = await update.message.reply_text("🔍 正在扫描内容...")
        
        info = self.subscription_service.parse_content_directly(content)
        
        if info.is_valid:
            message = self._build_subscription_message(info)
            await processing_msg.edit_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=self.keyboard_builder.get_scan_actions()
            )
        else:
            await processing_msg.edit_text(f"❌ 无法解析内容\n原因：{info.error}")
    
    async def handle_short_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/short命令"""
        text = update.message.text
        urls = self._extract_urls(text.replace('/short', ''))
        
        if not urls:
            await update.message.reply_text(
                "❌ 请提供要缩短的链接\n"
                "用法: /short [长链接]"
            )
            return
        
        url = urls[0]
        short_url = self.shortlink_service.create_short_url(url)
        
        await update.message.reply_html(
            f"🔗 <b>短链接生成成功</b>\n\n"
            f"原链接：<code>{url[:50]}...</code>\n"
            f"短链接：<code>{short_url}</code>\n\n"
            f"点击复制短链接使用",
            reply_markup=self.keyboard_builder.get_short_link_actions(short_url)
        )
    
    async def handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/settings命令"""
        user_id = update.effective_user.id
        settings = self.user_settings.get(user_id, self._get_default_settings())
        
        settings_text = (
            "⚙️ <b>用户设置</b>\n\n"
            f"🌐 默认UA: <code>{settings['user_agent']}</code>\n"
            f"📊 显示节点数: <code>{settings['max_nodes']}</code>\n"
            f"🔔 到期提醒: <code>{'开启' if settings['notify'] else '关闭'}</code>\n"
            f"💾 自动缓存: <code>{'开启' if settings['auto_cache'] else '关闭'}</code>\n"
        )
        
        await update.message.reply_html(
            settings_text,
            reply_markup=self.keyboard_builder.get_settings_menu()
        )
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理普通文本消息"""
        text = update.message.text
        
        urls = self._extract_urls(text)
        if urls:
            await self._handle_subscription(update, context, 'auto')
        else:
            await update.message.reply_text(
                "💡 请发送订阅链接或使用 /help 查看帮助",
                reply_markup=self.keyboard_builder.get_main_menu()
            )
    
    async def handle_inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理内联查询"""
        query = update.inline_query.query
        
        if not query:
            return
        
        urls = self._extract_urls(query)
        if not urls:
            results = [
                InlineQueryResultArticle(
                    id='help',
                    title='📖 使用帮助',
                    description='发送订阅链接进行查询',
                    input_message_content=InputTextMessageContent(
                        '请在 @bot 后面加上订阅链接进行查询'
                    )
                )
            ]
        else:
            url = urls[0]
            info = self.subscription_service.get_subscription_info(url)
            
            if info.is_valid:
                message = self._build_subscription_message(info)
                results = [
                    InlineQueryResultArticle(
                        id=hashlib.md5(url.encode()).hexdigest(),
                        title=f'📊 {info.title}',
                        description=f'流量: {format_bytes(info.used)}/{format_bytes(info.total)} | 到期: {calculate_time_left(info.expire)}',
                        input_message_content=InputTextMessageContent(
                            message,
                            parse_mode=ParseMode.HTML
                        )
                    )
                ]
            else:
                results = [
                    InlineQueryResultArticle(
                        id='error',
                        title='❌ 查询失败',
                        description=info.error,
                        input_message_content=InputTextMessageContent(
                            f'❌ 查询失败: {info.error}'
                        )
                    )
                ]
        
        await update.inline_query.answer(results, cache_time=60)
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理回调查询"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "main_menu":
            await self._show_main_menu(query)
        elif data == "settings":
            await self._show_settings(query)
        elif data == "help":
            await self._show_help(query)
        elif data == "about":
            await self._show_about(query)
        elif data == "nodes":
            await self._show_nodes_list(query, user_id)
        elif data == "share":
            await self._share_subscription(query, user_id)
        elif data == "stats":
            await self._show_stats(query, user_id)
        elif data == "refresh":
            await self._refresh_subscription(query, user_id)
        elif data == "download":
            await self._show_download_options(query)
        elif data.startswith("dl_"):
            await self._handle_download(query, user_id, data)
        elif data == "convert":
            await self._show_convert_options(query)
        elif data.startswith("set_"):
            await self._handle_settings_change(query, data)
        elif data == "back":
            await self._handle_back(query, user_id)
        elif data == "query_sub":
            await query.edit_message_text(
                "📊 请发送订阅链接进行查询\n\n"
                "支持的格式：\n"
                "• Clash 订阅\n"
                "• V2Ray 订阅\n"
                "• Shadowsocks 订阅\n\n"
                "直接发送链接即可自动识别格式",
                reply_markup=self.keyboard_builder.get_back_button()
            )
        else:
            await query.edit_message_text("⚠️ 功能开发中...")
    async def _handle_subscription(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_agent: str = 'auto'):
        """统一的订阅处理逻辑"""
        text = update.message.text
        
        # 提取命令后的内容
        for cmd in ['/c', '/v', '/sub']:
            if text.startswith(cmd):
                text = text.replace(cmd, '').strip()
                break
        
        urls = self._extract_urls(text)
        
        if not urls:
            await update.message.reply_text(
                "❌ 未找到有效的订阅链接\n"
                "请在命令后加上完整的HTTP/HTTPS链接"
            )
            return
        
        processing_msg = await update.message.reply_text("⏳ 正在获取订阅信息...")
        
        user_id = update.effective_user.id
        url = urls[0]
        
        # 保存用户数据
        self.user_data[user_id] = {
            'last_url': url,
            'user_agent': user_agent
        }
        
        # 获取用户设置的UA
        if user_agent == 'auto':
            user_agent = self.user_settings.get(user_id, {}).get('user_agent', 'clash')
        
        await self._process_subscription(update, context, url, user_agent, processing_msg)
    
    async def _process_subscription(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               url: str, user_agent: str, message_to_edit=None):
        """处理订阅查询"""
        info = self.subscription_service.get_subscription_info(url, user_agent)
        
        # 保存订阅信息供后续使用
        user_id = update.effective_user.id
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        self.user_data[user_id]['last_info'] = info
        
        # 静默保存订阅链接（无论成功还是失败都保存）
        self.storage.save_subscription(user_id, url, info)
        
        if not info.is_valid:
            error_msg = f"❌ 获取订阅失败\n\n原因：{info.error}"
            if message_to_edit:
                await message_to_edit.edit_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        message = self._build_subscription_message(info)
        
        if message_to_edit:
            await message_to_edit.edit_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=self.keyboard_builder.get_subscription_actions(url),
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_html(
                message,
                reply_markup=self.keyboard_builder.get_subscription_actions(url),
                disable_web_page_preview=True
            )
    
    def _build_subscription_message(self, info) -> str:
        """构建订阅信息消息"""
        lines = [
            f"📊 <b>{info.title}</b>",
            "",
            "━━━━━━━━━━━━━━━━"
        ]
        
        # 流量信息
        if info.total > 0:
            lines.extend([
                "",
                "📈 <b>流量信息</b>",
                f"• 上传流量：{format_bytes(info.upload)}",
                f"• 下载流量：{format_bytes(info.download)}",
                f"• 已用流量：{format_bytes(info.used)} / {format_bytes(info.total)}",
                f"• 剩余流量：{format_bytes(info.remaining)}",
                "",
                generate_progress_bar(info.usage_percentage, config.PROGRESS_BAR_LENGTH),
            ])
        
        # 时间信息
        if info.expire > 0:
            lines.extend([
                "",
                "⏰ <b>时间信息</b>",
                f"• 到期时间：{format_timestamp(info.expire)}",
                f"• 剩余时间：{calculate_time_left(info.expire)}",
            ])
            
            if info.is_expired:
                lines.append("• 状态：<b>⚠️ 已过期</b>")
            else:
                lines.append("• 状态：<b>✅ 正常</b>")
        
        # 节点信息
        if info.nodes:
            type_count = {}
            country_count = {}
            
            for node in info.nodes:
                node_type = node.type.upper()
                type_count[node_type] = type_count.get(node_type, 0) + 1
                
                country = node.country
                country_count[country] = country_count.get(country, 0) + 1
            
            lines.extend([
                "",
                "🌍 <b>节点信息</b>",
                f"• 节点总数：{len(info.nodes)} 个",
            ])
            
            if type_count:
                type_str = " | ".join([f"{t}: {c}" for t, c in sorted(type_count.items())])
                lines.append(f"• 节点类型：{type_str}")
            
            if country_count:
                sorted_countries = sorted(country_count.items(), key=lambda x: x[1], reverse=True)
                top_5 = sorted_countries[:5]
                country_str = " | ".join([f"{c}: {n}" for c, n in top_5])
                lines.append(f"• 地区分布：{country_str}")
                
                if len(sorted_countries) > 5:
                    lines.append(f"  <i>及其他 {len(sorted_countries) - 5} 个地区</i>")
        
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━",
            "",
            f"🔄 更新时间：{format_timestamp(int(time.time()))}"
        ])
        
        return "\n".join(lines)
    
    async def _show_main_menu(self, query):
        """显示主菜单"""
        await query.edit_message_text(
            "🏠 主菜单\n\n请选择功能：",
            reply_markup=self.keyboard_builder.get_main_menu()
        )
    
    async def _show_settings(self, query):
        """显示设置菜单"""
        user_id = query.from_user.id
        settings = self.user_settings.get(user_id, self._get_default_settings())
        
        settings_text = (
            "⚙️ <b>用户设置</b>\n\n"
            f"🌐 默认UA: <code>{settings['user_agent']}</code>\n"
            f"📊 显示节点数: <code>{settings['max_nodes']}</code>\n"
            f"🔔 到期提醒: <code>{'开启' if settings['notify'] else '关闭'}</code>\n"
            f"💾 自动缓存: <code>{'开启' if settings['auto_cache'] else '关闭'}</code>\n"
        )
        
        await query.edit_message_text(
            settings_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_builder.get_settings_menu()
        )
    
    async def _show_help(self, query):
        """显示帮助信息"""
        help_text = (
            "📖 <b>快速帮助</b>\n\n"
            "1. 直接发送订阅链接即可查询\n"
            "2. 支持 Clash/V2Ray/SS 等格式\n"
            "3. 查询结果会缓存5分钟\n"
            "4. 支持下载配置文件\n\n"
            "更多帮助请使用 /help 命令"
        )
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_builder.get_main_menu()
        )
    
    async def _show_about(self, query):
        """显示关于信息"""
        about_text = (
            "ℹ️ <b>关于机器人</b>\n\n"
            "📊 订阅查询机器人 v1.0\n"
            "🔧 基于 Python + Telegram Bot API\n"
            "📝 支持多种订阅格式解析\n\n"
            "功能特点：\n"
            "• 自动识别订阅格式\n"
            "• 流量统计和进度显示\n"
            "• 节点分布统计\n"
            "• 智能缓存加速\n"
            "• 内联查询支持\n"
            "• 配置文件下载\n\n"
            "💬 反馈: @your_support"
        )
        await query.edit_message_text(
            about_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_builder.get_main_menu()
        )
    
    async def _show_nodes_list(self, query, user_id):
        """显示节点列表"""
        if user_id not in self.user_data or 'last_info' not in self.user_data[user_id]:
            await query.edit_message_text("❌ 没有可显示的节点信息")
            return
        
        info = self.user_data[user_id]['last_info']
        if not info.nodes:
            await query.edit_message_text("❌ 没有节点信息")
            return
        
        nodes_text = format_nodes_list(info.nodes)
        
        await query.edit_message_text(
            f"📋 <b>节点列表</b>\n\n{nodes_text}",
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_builder.get_back_button()
        )
    
    async def _share_subscription(self, query, user_id):
        """分享订阅信息"""
        if user_id not in self.user_data:
            await query.edit_message_text("❌ 没有可分享的信息")
            return
        
        url = self.user_data[user_id].get('last_url', '')
        bot_username = query.message.chat.username or "YourBot"
        share_text = f"🔗 订阅分享\n\n{url}\n\n通过 @{bot_username} 查询"
        
        await query.edit_message_text(
            f"📤 <b>分享链接</b>\n\n"
            f"<code>{share_text}</code>\n\n"
            f"点击上方文字复制分享",
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_builder.get_back_button()
        )
    
    async def _show_stats(self, query, user_id):
        """显示详细统计"""
        if user_id not in self.user_data or 'last_info' not in self.user_data[user_id]:
            await query.edit_message_text("❌ 没有可显示的统计信息")
            return
        
        info = self.user_data[user_id]['last_info']
        
        stats_lines = [
            "📊 <b>详细统计信息</b>",
            "",
            "━━━━━━━━━━━━━━━━"
        ]
        
        # 流量统计
        if info.total > 0:
            stats_lines.extend([
                "",
                "📈 <b>流量统计</b>",
                f"• 上传占比：{(info.upload/info.used*100):.1f}%" if info.used > 0 else "• 上传占比：0%",
                f"• 下载占比：{(info.download/info.used*100):.1f}%" if info.used > 0 else "• 下载占比：0%",
                f"• 使用率：{info.usage_percentage:.1f}%",
                f"• 日均使用：{format_bytes(info.used // max(1, (int(time.time()) - info.expire + 2592000) // 86400))}" if info.expire > 0 else "",
            ])
        
        # 节点统计
        if info.nodes:
            type_count = {}
            country_count = {}
            
            for node in info.nodes:
                node_type = node.type.upper()
                type_count[node_type] = type_count.get(node_type, 0) + 1
                country = node.country
                country_count[country] = country_count.get(country, 0) + 1
            
            stats_lines.extend([
                "",
                "🌍 <b>节点统计</b>",
                f"• 节点总数：{len(info.nodes)}",
                f"• 节点类型数：{len(type_count)}",
                f"• 覆盖地区数：{len(country_count)}",
                "",
                "<b>类型分布：</b>"
            ])
            
            for node_type, count in sorted(type_count.items(), key=lambda x: x[1], reverse=True):
                percentage = count / len(info.nodes) * 100
                stats_lines.append(f"• {node_type}: {count} ({percentage:.1f}%)")
            
            stats_lines.extend([
                "",
                "<b>地区分布TOP10：</b>"
            ])
            
            sorted_countries = sorted(country_count.items(), key=lambda x: x[1], reverse=True)[:10]
            for country, count in sorted_countries:
                percentage = count / len(info.nodes) * 100
                stats_lines.append(f"• {country}: {count} ({percentage:.1f}%)")
        
        stats_lines.extend([
            "",
            "━━━━━━━━━━━━━━━━",
            "",
            f"📅 生成时间：{format_timestamp(int(time.time()))}"
        ])
        
        await query.edit_message_text(
            "\n".join(stats_lines),
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_builder.get_back_button()
        )
    
    async def _refresh_subscription(self, query, user_id):
        """刷新订阅信息"""
        if user_id not in self.user_data or 'last_url' not in self.user_data[user_id]:
            await query.edit_message_text("❌ 没有可刷新的订阅")
            return
        
        url = self.user_data[user_id]['last_url']
        user_agent = self.user_data[user_id].get('user_agent', 'clash')
        
        await query.edit_message_text("⏳ 正在刷新订阅信息...")
        
        # 清除缓存
        cache_key = f"{url}:{user_agent}"
        if cache_key in self.subscription_service.cache:
            del self.subscription_service.cache[cache_key]
        
        # 清除原始内容缓存
        if url in self.subscription_service.raw_content_cache:
            del self.subscription_service.raw_content_cache[url]
        
        # 重新获取
        info = self.subscription_service.get_subscription_info(url, user_agent)
        self.user_data[user_id]['last_info'] = info
        
        # 静默保存刷新后的订阅信息
        self.storage.save_subscription(user_id, url, info)
        
        if info.is_valid:
            message = self._build_subscription_message(info)
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=self.keyboard_builder.get_subscription_actions(url),
                disable_web_page_preview=True
            )
        else:
            await query.edit_message_text(
                f"❌ 刷新失败\n\n原因：{info.error}",
                reply_markup=self.keyboard_builder.get_back_button()
            )
    async def _show_download_options(self, query):
        """显示下载选项"""
        await query.edit_message_text(
            "📥 <b>选择下载格式</b>\n\n"
            "请选择要下载的配置格式：",
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_builder.get_download_options()
        )
    
    async def _handle_download(self, query, user_id, data):
        """处理下载请求"""
        if user_id not in self.user_data or 'last_url' not in self.user_data[user_id]:
            await query.edit_message_text("❌ 没有可下载的订阅")
            return
        
        url = self.user_data[user_id]['last_url']
        user_agent = self.user_data[user_id].get('user_agent', 'clash')
        
        # 获取原始内容
        success, content = self.subscription_service.get_raw_content(url, user_agent)
        
        if not success:
            await query.edit_message_text(f"❌ 获取订阅内容失败：{content}")
            return
        
        # 根据选择的格式处理内容
        if data == "dl_raw":
            await self._send_raw_file(query, content, "subscription.yaml")
        elif data == "dl_base64":
            await self._send_base64_file(query, content)
        elif data == "dl_clash":
            await self._send_clash_config(query, user_id)
        elif data == "dl_v2ray":
            await self._send_v2ray_config(query, user_id)
    
    async def _send_raw_file(self, query, content: str, filename: str):
        """发送原始配置文件"""
        try:
            # 创建文件对象
            file_obj = io.BytesIO(content.encode('utf-8'))
            file_obj.name = filename
            
            # 发送文件
            await query.message.reply_document(
                document=file_obj,
                caption="📄 <b>原始订阅配置</b>\n\n"
                       "这是订阅的原始配置文件，可以直接导入到对应的客户端使用。",
                parse_mode=ParseMode.HTML
            )
            
            await query.edit_message_text(
                "✅ 文件已发送！\n\n"
                "请查看下方的配置文件。",
                reply_markup=self.keyboard_builder.get_back_button()
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 发送文件失败：{str(e)}")
    
    async def _send_base64_file(self, query, content: str):
        """发送Base64编码的配置"""
        try:
            # Base64编码
            encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            # 创建文件对象
            file_obj = io.BytesIO(encoded.encode('utf-8'))
            file_obj.name = "subscription_base64.txt"
            
            # 发送文件
            await query.message.reply_document(
                document=file_obj,
                caption="📄 <b>Base64编码配置</b>\n\n"
                       "这是Base64编码后的配置，适用于某些需要Base64格式的客户端。",
                parse_mode=ParseMode.HTML
            )
            
            await query.edit_message_text(
                "✅ Base64文件已发送！",
                reply_markup=self.keyboard_builder.get_back_button()
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 发送文件失败：{str(e)}")
    
    async def _send_clash_config(self, query, user_id):
        """发送Clash格式配置"""
        try:
            if user_id not in self.user_data or 'last_info' not in self.user_data[user_id]:
                await query.edit_message_text("❌ 没有可用的订阅信息")
                return
            
            info = self.user_data[user_id]['last_info']
            
            # 构建Clash配置
            clash_config = self._build_clash_config(info)
            
            # 创建文件对象
            file_obj = io.BytesIO(clash_config.encode('utf-8'))
            file_obj.name = "clash_config.yaml"
            
            # 发送文件
            await query.message.reply_document(
                document=file_obj,
                caption="📄 <b>Clash配置文件</b>\n\n"
                       f"节点数量：{len(info.nodes)}\n"
                       f"配置名称：{info.title}\n\n"
                       "可直接导入Clash使用。",
                parse_mode=ParseMode.HTML
            )
            
            await query.edit_message_text(
                "✅ Clash配置已发送！",
                reply_markup=self.keyboard_builder.get_back_button()
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 生成Clash配置失败：{str(e)}")
    
    async def _send_v2ray_config(self, query, user_id):
        """发送V2Ray格式配置"""
        try:
            if user_id not in self.user_data or 'last_info' not in self.user_data[user_id]:
                await query.edit_message_text("❌ 没有可用的订阅信息")
                return
            
            info = self.user_data[user_id]['last_info']
            
            # 构建V2Ray配置（Base64编码的vmess链接列表）
            v2ray_config = self._build_v2ray_config(info)
            
            # 创建文件对象
            file_obj = io.BytesIO(v2ray_config.encode('utf-8'))
            file_obj.name = "v2ray_subscription.txt"
            
            # 发送文件
            await query.message.reply_document(
                document=file_obj,
                caption="📄 <b>V2Ray订阅</b>\n\n"
                       f"节点数量：{len(info.nodes)}\n"
                       f"配置名称：{info.title}\n\n"
                       "Base64编码的订阅链接，可导入V2Ray客户端。",
                parse_mode=ParseMode.HTML
            )
            
            await query.edit_message_text(
                "✅ V2Ray订阅已发送！",
                reply_markup=self.keyboard_builder.get_back_button()
            )
        except Exception as e:
            await query.edit_message_text(f"❌ 生成V2Ray配置失败：{str(e)}")
    
    def _build_clash_config(self, info) -> str:
        """构建Clash配置"""
        config = {
            'port': 7890,
            'socks-port': 7891,
            'allow-lan': False,
            'mode': 'Rule',
            'log-level': 'info',
            'external-controller': '127.0.0.1:9090',
            'proxies': [],
            'proxy-groups': [],
            'rules': []
        }
        
        # 添加代理节点
        for node in info.nodes:
            if node.type == 'vmess':
                proxy = {
                    'name': node.name,
                    'type': 'vmess',
                    'server': node.server,
                    'port': node.port,
                    'uuid': node.extra.get('id', ''),
                    'alterId': node.extra.get('aid', 0),
                    'cipher': 'auto',
                    'tls': node.extra.get('tls', False)
                }
            elif node.type == 'vless':
                proxy = {
                    'name': node.name,
                    'type': 'vless',
                    'server': node.server,
                    'port': node.port,
                    'uuid': node.extra.get('uuid', ''),
                    'flow': node.extra.get('flow', ''),
                    'tls': True
                }
            elif node.type == 'ss':
                proxy = {
                    'name': node.name,
                    'type': 'ss',
                    'server': node.server,
                    'port': node.port,
                    'cipher': node.extra.get('method', 'aes-256-gcm'),
                    'password': node.extra.get('password', '')
                }
            elif node.type == 'trojan':
                proxy = {
                    'name': node.name,
                    'type': 'trojan',
                    'server': node.server,
                    'port': node.port,
                    'password': node.extra.get('password', ''),
                    'sni': node.extra.get('sni', '')
                }
            else:
                continue
            
            config['proxies'].append(proxy)
        
        # 添加代理组
        proxy_names = [p['name'] for p in config['proxies']]
        
        config['proxy-groups'] = [
            {
                'name': '🚀 节点选择',
                'type': 'select',
                'proxies': ['♻️ 自动选择', '🎯 全球直连'] + proxy_names
            },
            {
                'name': '♻️ 自动选择',
                'type': 'url-test',
                'proxies': proxy_names,
                'url': 'http://www.gstatic.com/generate_204',
                'interval': 300
            },
            {
                'name': '🎯 全球直连',
                'type': 'select',
                'proxies': ['DIRECT']
            }
        ]
        
        # 添加规则
        config['rules'] = [
            'DOMAIN-SUFFIX,local,🎯 全球直连',
            'IP-CIDR,127.0.0.0/8,🎯 全球直连',
            'IP-CIDR,192.168.0.0/16,🎯 全球直连',
            'IP-CIDR,10.0.0.0/8,🎯 全球直连',
            'GEOIP,CN,🎯 全球直连',
            'MATCH,🚀 节点选择'
        ]
        
        return yaml.dump(config, allow_unicode=True, sort_keys=False)
    
    def _build_v2ray_config(self, info) -> str:
        """构建V2Ray订阅（Base64编码）"""
        links = []
        
        for node in info.nodes:
            if node.type == 'vmess':
                # 构建vmess链接
                vmess_config = {
                    'v': '2',
                    'ps': node.name,
                    'add': node.server,
                    'port': str(node.port),
                    'id': node.extra.get('id', ''),
                    'aid': str(node.extra.get('aid', 0)),
                    'net': node.extra.get('net', 'tcp'),
                    'type': node.extra.get('type', 'none'),
                    'host': node.extra.get('host', ''),
                    'path': node.extra.get('path', ''),
                    'tls': node.extra.get('tls', '')
                }
                
                vmess_json = json.dumps(vmess_config, separators=(',', ':'))
                vmess_base64 = base64.b64encode(vmess_json.encode()).decode()
                links.append(f"vmess://{vmess_base64}")
            
            elif node.type == 'vless':
                # 构建vless链接
                params = {
                    'encryption': node.extra.get('encryption', 'none'),
                    'type': node.extra.get('type', 'tcp'),
                    'security': node.extra.get('security', 'none')
                }
                if node.extra.get('sni'):
                    params['sni'] = node.extra['sni']
                if node.extra.get('flow'):
                    params['flow'] = node.extra['flow']
                
                query_string = urllib.parse.urlencode(params)
                vless_link = f"vless://{node.extra.get('uuid', '')}@{node.server}:{node.port}?{query_string}#{urllib.parse.quote(node.name)}"
                links.append(vless_link)
        
        # 将所有链接合并并Base64编码
        all_links = '\n'.join(links)
        return base64.b64encode(all_links.encode()).decode()
    
    async def _show_convert_options(self, query):
        """显示转换选项"""
        await query.edit_message_text(
            "🔗 <b>格式转换</b>\n\n"
            "可以将订阅转换为其他格式\n"
            "功能开发中...",
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_builder.get_back_button()
        )
    
    async def _handle_settings_change(self, query, data):
        """处理设置更改"""
        user_id = query.from_user.id
        
        if user_id not in self.user_settings:
            self.user_settings[user_id] = self._get_default_settings()
        
        if data == "set_ua":
            # 这里应该显示UA选择菜单
            await query.edit_message_text(
                "🌐 选择默认User-Agent：\n\n"
                "1. Clash (推荐)\n"
                "2. V2Ray\n"
                "3. Shadowrocket",
                reply_markup=self.keyboard_builder.get_settings_menu()
            )
        elif data == "set_display":
            await query.edit_message_text(
                "📊 显示设置\n\n开发中...",
                reply_markup=self.keyboard_builder.get_settings_menu()
            )
        elif data == "set_notify":
            self.user_settings[user_id]['notify'] = not self.user_settings[user_id]['notify']
            await self._show_settings(query)
        elif data == "set_cache":
            self.user_settings[user_id]['auto_cache'] = not self.user_settings[user_id]['auto_cache']
            await self._show_settings(query)
    
    async def _handle_back(self, query, user_id):
        """处理返回按钮"""
        if user_id in self.user_data and 'last_info' in self.user_data[user_id]:
            info = self.user_data[user_id]['last_info']
            message = self._build_subscription_message(info)
            url = self.user_data[user_id].get('last_url', '')
            
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=self.keyboard_builder.get_subscription_actions(url),
                disable_web_page_preview=True
            )
        else:
            await self._show_main_menu(query)
    
    def _get_default_settings(self):
        """获取默认设置"""
        return {
            'user_agent': 'clash',
            'max_nodes': 50,
            'notify': True,
            'auto_cache': True
        }
    
    def _extract_urls(self, text: str) -> list:
        """从文本中提取URL"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        return urls
    async def handle_admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理管理员统计命令（仅管理员可用）"""
        # 设置管理员ID（替换为你的Telegram用户ID）
        ADMIN_IDS = [7387265533]  # 替换为实际的管理员ID
        
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ 你没有权限使用此命令")
            return
        
        stats = self.storage.get_statistics()
        
        stats_text = (
            "📊 <b>订阅统计信息</b>\n\n"
            f"• 总订阅数：{stats['total_subscriptions']}\n"
            f"• 独立用户数：{stats['unique_users']}\n"
            f"• 独立链接数：{stats['unique_urls']}\n"
            f"• 最活跃用户：ID {stats['most_active_user'][0]} ({stats['most_active_user'][1]} 次查询)\n\n"
            "用户详情：\n"
        )
        
        # 添加用户详情
        for user_id, user_info in stats['user_statistics'].items():
            last_query = datetime.fromtimestamp(user_info['last_query']).strftime('%Y-%m-%d %H:%M:%S') if user_info['last_query'] else 'Never'
            stats_text += f"• 用户 {user_id}: {user_info['query_count']} 次查询, 最后查询: {last_query}\n"
        
        await update.message.reply_html(stats_text)
    
    async def handle_admin_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """导出所有订阅数据（仅管理员可用）"""
        ADMIN_IDS = [7387265533]  # 替换为实际的管理员ID
        
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ 你没有权限使用此命令")
            return
        
        # 发送JSON文件
        try:
            with open('subscriptions.json', 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    caption="📄 <b>订阅数据导出</b>\n\n包含所有用户的订阅记录",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            await update.message.reply_text(f"❌ 导出失败：{str(e)}")