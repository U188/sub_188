# utils/storage.py
import json
import os
import time
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SubscriptionStorage:
    """订阅链接存储管理"""
    
    def __init__(self, storage_file: str = "subscriptions.json"):
        self.storage_file = storage_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        """加载存储的数据"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载存储文件失败: {e}")
                return {"subscriptions": [], "users": {}}
        return {"subscriptions": [], "users": {}}
    
    def _save_data(self):
        """保存数据到文件"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存存储文件失败: {e}")
    
    def save_subscription(self, user_id: int, url: str, info: dict = None):
        """
        静默保存订阅链接
        
        Args:
            user_id: 用户ID
            url: 订阅链接
            info: 订阅信息（可选）
        """
        try:
            # 准备订阅记录
            subscription_record = {
                "url": url,
                "user_id": user_id,
                "timestamp": int(time.time()),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            
            # 如果有订阅信息，添加额外字段
            if info:
                subscription_record.update({
                    "title": getattr(info, 'title', '未命名订阅'),
                    "total_traffic": getattr(info, 'total', 0),
                    "used_traffic": getattr(info, 'used', 0),
                    "expire_time": getattr(info, 'expire', 0),
                    "node_count": len(getattr(info, 'nodes', [])),
                    "is_valid": getattr(info, 'is_valid', False)
                })
            
            # 检查是否已存在相同的URL
            existing_index = None
            for i, sub in enumerate(self.data["subscriptions"]):
                if sub["url"] == url and sub["user_id"] == user_id:
                    existing_index = i
                    break
            
            if existing_index is not None:
                # 更新现有记录
                self.data["subscriptions"][existing_index] = subscription_record
            else:
                # 添加新记录
                self.data["subscriptions"].append(subscription_record)
            
            # 更新用户统计
            user_key = str(user_id)
            if user_key not in self.data["users"]:
                self.data["users"][user_key] = {
                    "first_seen": int(time.time()),
                    "query_count": 0,
                    "last_query": None
                }
            
            self.data["users"][user_key]["query_count"] += 1
            self.data["users"][user_key]["last_query"] = int(time.time())
            
            # 保存到文件
            self._save_data()
            
            logger.info(f"已保存订阅: 用户 {user_id}, URL: {url[:50]}...")
            
        except Exception as e:
            logger.error(f"保存订阅失败: {e}")
    
    def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """获取用户的所有订阅"""
        return [
            sub for sub in self.data["subscriptions"] 
            if sub["user_id"] == user_id
        ]
    
    def get_all_subscriptions(self) -> List[Dict]:
        """获取所有订阅"""
        return self.data["subscriptions"]
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total_subs = len(self.data["subscriptions"])
        unique_users = len(set(sub["user_id"] for sub in self.data["subscriptions"]))
        unique_urls = len(set(sub["url"] for sub in self.data["subscriptions"]))
        
        # 按用户统计
        user_stats = {}
        for sub in self.data["subscriptions"]:
            user_id = sub["user_id"]
            if user_id not in user_stats:
                user_stats[user_id] = 0
            user_stats[user_id] += 1
        
        # 最活跃用户
        most_active_user = max(user_stats.items(), key=lambda x: x[1]) if user_stats else (None, 0)
        
        return {
            "total_subscriptions": total_subs,
            "unique_users": unique_users,
            "unique_urls": unique_urls,
            "most_active_user": most_active_user,
            "user_statistics": self.data.get("users", {})
        }
    
    def cleanup_old_records(self, days: int = 30):
        """清理旧记录"""
        cutoff_time = int(time.time()) - (days * 86400)
        original_count = len(self.data["subscriptions"])
        
        self.data["subscriptions"] = [
            sub for sub in self.data["subscriptions"]
            if sub.get("timestamp", 0) > cutoff_time
        ]
        
        removed_count = original_count - len(self.data["subscriptions"])
        if removed_count > 0:
            self._save_data()
            logger.info(f"清理了 {removed_count} 条旧记录")
        
        return removed_count