# services/parsers.py
import base64
import json
import yaml
import re
import urllib.parse
from abc import ABC, abstractmethod
from typing import List, Optional
from models.subscription import NodeInfo

class BaseParser(ABC):
    """解析器基类"""
    
    @abstractmethod
    def can_parse(self, content: str) -> bool:
        pass
    
    @abstractmethod
    def parse(self, content: str) -> List[NodeInfo]:
        pass
    
    def extract_country(self, name: str) -> str:
        """从节点名称中提取国家/地区信息"""
        country_patterns = {
            '香港': ['香港', 'HK', 'Hong Kong', '🇭🇰'],
            '台湾': ['台湾', 'TW', 'Taiwan', '🇹🇼'],
            '新加坡': ['新加坡', 'SG', 'Singapore', '🇸🇬'],
            '日本': ['日本', 'JP', 'Japan', '🇯🇵'],
            '美国': ['美国', 'US', 'USA', '🇺🇸'],
            '韩国': ['韩国', 'KR', 'Korea', '🇰🇷'],
            '英国': ['英国', 'UK', 'Britain', '🇬🇧'],
            '德国': ['德国', 'DE', 'Germany', '🇩🇪'],
            '法国': ['法国', 'FR', 'France', '🇫🇷'],
            '加拿大': ['加拿大', 'CA', 'Canada', '🇨🇦'],
            '澳大利亚': ['澳大利亚', 'AU', 'Australia', '🇦🇺'],
            '俄罗斯': ['俄罗斯', 'RU', 'Russia', '🇷🇺'],
            '印度': ['印度', 'IN', 'India', '🇮🇳'],
            '土耳其': ['土耳其', 'TR', 'Turkey', '🇹🇷'],
            '阿根廷': ['阿根廷', 'AR', 'Argentina', '🇦🇷'],
            '荷兰': ['荷兰', 'NL', 'Netherlands', '🇳🇱'],
        }
        
        name_upper = name.upper()
        for country, patterns in country_patterns.items():
            for pattern in patterns:
                if pattern.upper() in name_upper:
                    return country
        
        return "其他"

class ClashParser(BaseParser):
    """Clash配置解析器"""
    
    def can_parse(self, content: str) -> bool:
        try:
            data = yaml.safe_load(content)
            return isinstance(data, dict) and 'proxies' in data
        except:
            return False
    
    def parse(self, content: str) -> List[NodeInfo]:
        nodes = []
        try:
            data = yaml.safe_load(content)
            proxies = data.get('proxies', [])
            
            for proxy in proxies:
                if not isinstance(proxy, dict):
                    continue
                
                node = NodeInfo(
                    name=proxy.get('name', 'Unknown'),
                    type=proxy.get('type', 'unknown').lower(),
                    server=proxy.get('server', ''),
                    port=proxy.get('port', 0),
                    country=self.extract_country(proxy.get('name', '')),
                    extra={
                        'uuid': proxy.get('uuid'),
                        'alterId': proxy.get('alterId'),
                        'cipher': proxy.get('cipher'),
                        'tls': proxy.get('tls'),
                        'network': proxy.get('network'),
                    }
                )
                nodes.append(node)
                
        except Exception as e:
            print(f"Clash解析错误: {e}")
        
        return nodes

class V2RayParser(BaseParser):
    """V2Ray配置解析器"""
    
    def can_parse(self, content: str) -> bool:
        try:
            decoded = base64.b64decode(content).decode('utf-8')
            return 'vmess://' in decoded or 'vless://' in decoded
        except:
            return False
    
    def parse(self, content: str) -> List[NodeInfo]:
        nodes = []
        try:
            decoded = base64.b64decode(content).decode('utf-8')
            lines = decoded.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('vmess://'):
                    node = self._parse_vmess(line)
                    if node:
                        nodes.append(node)
                elif line.startswith('vless://'):
                    node = self._parse_vless(line)
                    if node:
                        nodes.append(node)
                        
        except Exception as e:
            print(f"V2Ray解析错误: {e}")
        
        return nodes
    
    def _parse_vmess(self, uri: str) -> Optional[NodeInfo]:
        try:
            content = uri.replace('vmess://', '')
            decoded = base64.b64decode(content + '==').decode('utf-8')
            config = json.loads(decoded)
            
            return NodeInfo(
                name=config.get('ps', 'Unknown'),
                type='vmess',
                server=config.get('add', ''),
                port=int(config.get('port', 0)),
                country=self.extract_country(config.get('ps', '')),
                extra={
                    'id': config.get('id'),
                    'aid': config.get('aid'),
                    'net': config.get('net'),
                    'tls': config.get('tls'),
                }
            )
        except:
            return None
    
    def _parse_vless(self, uri: str) -> Optional[NodeInfo]:
        try:
            parsed = urllib.parse.urlparse(uri)
            server = parsed.hostname or ''
            port = parsed.port or 443
            params = urllib.parse.parse_qs(parsed.query)
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else 'VLESS'
            
            return NodeInfo(
                name=name,
                type='vless',
                server=server,
                port=port,
                country=self.extract_country(name),
                extra={
                    'uuid': parsed.username,
                    'encryption': params.get('encryption', ['none'])[0],
                    'type': params.get('type', ['tcp'])[0],
                    'security': params.get('security', ['none'])[0],
                }
            )
        except:
            return None

class ParserFactory:
    """解析器工厂"""
    
    def __init__(self):
        self.parsers = [
            ClashParser(),
            V2RayParser(),
        ]
    
    def parse_content(self, content: str) -> List[NodeInfo]:
        for parser in self.parsers:
            if parser.can_parse(content):
                return parser.parse(content)
        return []