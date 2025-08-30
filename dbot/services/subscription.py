# services/subscription.py
import requests
import base64
import time
import logging
from typing import Optional, Tuple
from models.subscription import SubscriptionInfo
from services.parsers import ParserFactory
from config import config

logger = logging.getLogger(__name__)

class SubscriptionService:
    """订阅服务核心类"""
    
    def __init__(self):
        self.parser_factory = ParserFactory()
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        self.cache = {}
        self.raw_content_cache = {}  # 新增原始内容缓存
    
    def get_subscription_info(self, url: str, user_agent: str = 'clash') -> SubscriptionInfo:
        """获取订阅信息"""
        # 检查缓存
        cache_key = f"{url}:{user_agent}"
        if cache_key in self.cache:
            cached_time, cached_info = self.cache[cache_key]
            if time.time() - cached_time < config.CACHE_TTL:
                return cached_info
        
        info = SubscriptionInfo(url=url)
        
        headers = {
            'User-Agent': config.USER_AGENTS.get(user_agent, config.USER_AGENTS['clash'])
        }
        
        try:
            response = self._fetch_subscription(url, headers)
            if not response:
                info.error = "无法获取订阅内容"
                return info
            
            # 缓存原始内容
            self.raw_content_cache[url] = response.text
            
            self._parse_headers(response, info)
            
            if response.text:
                self._parse_content(response.text, info)
            
            # 缓存结果
            if info.is_valid:
                self.cache[cache_key] = (time.time(), info)
            
        except Exception as e:
            logger.error(f"获取订阅信息失败: {e}")
            info.error = f"处理订阅时发生错误: {str(e)}"
        
        return info
    
    def get_raw_content(self, url: str, user_agent: str = 'clash') -> Tuple[bool, str]:
        """获取原始订阅内容"""
        # 先检查缓存
        if url in self.raw_content_cache:
            return True, self.raw_content_cache[url]
        
        headers = {
            'User-Agent': config.USER_AGENTS.get(user_agent, config.USER_AGENTS['clash'])
        }
        
        try:
            response = self._fetch_subscription(url, headers)
            if response and response.text:
                self.raw_content_cache[url] = response.text
                return True, response.text
            return False, "无法获取订阅内容"
        except Exception as e:
            return False, f"获取失败: {str(e)}"
    
    def parse_content_directly(self, content: str) -> SubscriptionInfo:
        """直接解析内容"""
        info = SubscriptionInfo()
        
        try:
            # 尝试Base64解码
            try:
                decoded = base64.b64decode(content).decode('utf-8')
                content = decoded
            except:
                pass
            
            self._parse_content(content, info)
            
            if not info.nodes:
                info.error = "未能解析出有效节点"
            
        except Exception as e:
            info.error = f"解析失败: {str(e)}"
        
        return info
    
    def _fetch_subscription(self, url: str, headers: dict) -> Optional[requests.Response]:
        """获取订阅内容"""
        for attempt in range(config.MAX_RETRIES):
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=config.REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{config.MAX_RETRIES}): {e}")
                if attempt == config.MAX_RETRIES - 1:
                    raise
                time.sleep(1)
        
        return None
    
    def _parse_headers(self, response: requests.Response, info: SubscriptionInfo):
        """解析HTTP响应头"""
        userinfo = response.headers.get('subscription-userinfo', '')
        if userinfo:
            self._parse_userinfo(userinfo, info)
        
        title = response.headers.get('profile-title', '')
        if title:
            try:
                info.title = base64.b64decode(title).decode('utf-8')
            except:
                info.title = title
        
        # 保存更新间隔
        update_interval = response.headers.get('profile-update-interval', '')
        if update_interval:
            info.extra = info.extra or {}
            info.extra['update_interval'] = update_interval
    
    def _parse_userinfo(self, userinfo: str, info: SubscriptionInfo):
        """解析subscription-userinfo头"""
        try:
            parts = userinfo.replace(' ', '').split(';')
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == 'upload':
                        info.upload = int(value)
                    elif key == 'download':
                        info.download = int(value)
                    elif key == 'total':
                        info.total = int(value)
                    elif key == 'expire':
                        info.expire = int(value)
        except Exception as e:
            logger.error(f"解析userinfo失败: {e}")
    
    def _parse_content(self, content: str, info: SubscriptionInfo):
        """解析订阅内容"""
        try:
            nodes = self.parser_factory.parse_content(content)
            info.nodes = nodes
        except Exception as e:
            logger.error(f"解析订阅内容失败: {e}")