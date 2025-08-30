# utils/formatters.py
import time
from datetime import datetime
from typing import List
from models.subscription import NodeInfo

def format_bytes(size_bytes: int) -> str:
    """将字节转换为人类可读格式"""
    if size_bytes < 0:
        return "N/A"
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"

def format_timestamp(timestamp: int) -> str:
    """格式化时间戳"""
    if timestamp == 0:
        return "永不过期"
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return "时间格式错误"

def calculate_time_left(timestamp: int) -> str:
    """计算剩余时间"""
    if timestamp == 0:
        return "无限期"
    
    now = int(time.time())
    diff = timestamp - now
    
    if diff <= 0:
        return "已过期"
    
    days = diff // 86400
    hours = (diff % 86400) // 3600
    minutes = (diff % 3600) // 60
    
    if days > 365:
        years = days // 365
        return f"{years}年{days % 365}天"
    elif days > 0:
        return f"{days}天{hours}小时"
    elif hours > 0:
        return f"{hours}小时{minutes}分钟"
    else:
        return f"{minutes}分钟"

def generate_progress_bar(percentage: float, length: int = 20) -> str:
    """生成文本进度条"""
    percentage = max(0, min(100, percentage))
    filled = int(length * percentage / 100)
    
    if percentage < 50:
        fill_char = '▓'
        empty_char = '░'
    elif percentage < 80:
        fill_char = '█'
        empty_char = '▒'
    else:
        fill_char = '█'
        empty_char = '░'
    
    bar = fill_char * filled + empty_char * (length - filled)
    return f"[{bar}] {percentage:.1f}%"

def format_nodes_list(nodes: List[NodeInfo], max_display: int = 50) -> str:
    """格式化节点列表显示"""
    if not nodes:
        return "暂无节点"
    
    lines = []
    display_nodes = nodes[:max_display]
    
    # 按类型分组
    grouped = {}
    for node in display_nodes:
        node_type = node.type.upper()
        if node_type not in grouped:
            grouped[node_type] = []
        grouped[node_type].append(node)
    
    # 格式化输出
    for node_type, type_nodes in grouped.items():
        lines.append(f"\n<b>【{node_type}节点】</b>")
        for i, node in enumerate(type_nodes, 1):
            node_line = f"{i}. {node.name}"
            if node.country != "其他":
                node_line += f" [{node.country}]"
            lines.append(node_line)
    
    if len(nodes) > max_display:
        lines.append(f"\n<i>... 还有 {len(nodes) - max_display} 个节点未显示</i>")
    
    return "\n".join(lines)