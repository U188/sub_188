# models/subscription.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class NodeInfo:
    """节点信息"""
    name: str
    type: str
    server: str
    port: int
    country: str = "Unknown"
    region: str = "Unknown"
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SubscriptionInfo:
    """订阅信息"""
    upload: int = 0
    download: int = 0
    total: int = 0
    expire: int = 0
    nodes: List[NodeInfo] = field(default_factory=list)
    url: str = ""
    title: str = "未命名订阅"
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def used(self) -> int:
        return self.upload + self.download
    
    @property
    def remaining(self) -> int:
        return max(0, self.total - self.used)
    
    @property
    def usage_percentage(self) -> float:
        if self.total == 0:
            return 0
        return min(100, (self.used / self.total) * 100)
    
    @property
    def is_expired(self) -> bool:
        if self.expire == 0:
            return False
        return datetime.now().timestamp() > self.expire
    
    @property
    def is_valid(self) -> bool:
        return self.error is None