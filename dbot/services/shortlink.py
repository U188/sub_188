# services/shortlink.py
import hashlib
import time

class ShortLinkService:
    """短链接服务"""
    
    def __init__(self):
        self.url_map = {}
    
    def create_short_url(self, long_url: str) -> str:
        """创建短链接"""
        hash_obj = hashlib.md5(f"{long_url}{time.time()}".encode())
        short_code = hash_obj.hexdigest()[:8]
        
        self.url_map[short_code] = long_url
        
        return f"https://t.me/YourBot?start={short_code}"
    
    def get_long_url(self, short_code: str) -> str:
        """获取原始链接"""
        return self.url_map.get(short_code, "")