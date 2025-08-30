import os
import re
import yaml # 确保已安装 PyYAML (pip install pyyaml)
import json
import random
import tempfile
import unicodedata # <--- 确保导入
from functools import wraps
from typing import Optional, List, Dict, Any, Union
from flask import Flask, request, jsonify, Blueprint, Response

# --- App Initialization ---
app = Flask(__name__)

# --- Configuration Layer (SOLID - Single Responsibility) ---
class Config:
    """集中化配置管理，遵循单一职责原则"""
    PROXIES_FILE_PATH = './all_proxies.txt'
    ALLOWED_UA_KEYWORDS = ['clash', 'Surge', 'Quantumult', 'Loon', 'Shadowrocket', 'clash-verge', 'sing-box']
    SECRET_PATH_PREFIX = '/u1888'
# --- Data Access & Processing Layer (SOLID - Interface Segregation) ---
class ProxyRepository:
    """代理数据仓库，遵循接口隔离原则"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
    
    def get_all_proxies(self) -> List[dict]:
        """获取所有代理配置"""
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                proxies = yaml.safe_load(f)
                if not isinstance(proxies, list):
                    print(f"Warning: {self.file_path} is not a YAML list. Content: {proxies}")
                    return []
                
                # 添加国家信息（遵循单一职责原则）
                for proxy in proxies:
                    if isinstance(proxy, dict) and 'name' in proxy:
                        country_match = re.match(r'([A-Z]{2})', proxy['name'])
                        proxy['country'] = country_match.group(1) if country_match else 'UNKNOWN'
                return proxies
        except (yaml.YAMLError, IOError) as e:
            print(f"Error reading or parsing YAML file: {e}")
            return []
    
    def save_proxies(self, proxies: List[dict]) -> bool:
        """保存代理配置"""
        proxies_to_save = [{k: v for k, v in p.items() if k != 'country'} for p in proxies]
        try:
            temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(self.file_path)))
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as temp_f:
                yaml.dump(proxies_to_save, temp_f, allow_unicode=True, sort_keys=False)
            os.rename(temp_path, self.file_path)
            return True
        except Exception as e:
            print(f"Error saving proxies to YAML: {e}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return False
# --- Proxy Format Conversion Layer (SOLID - Open/Closed Principle) ---
class FormatConverter:
    """格式转换器，遵循开放/封闭原则"""
    
    # 类型映射表（遵循 DRY 原则）
    TYPE_MAPPING = {
        'ss': 'shadowsocks',
        'vmess': 'vmess',
        'vless': 'vless', 
        'trojan': 'trojan',
        'hysteria2': 'hysteria2',
        'ssr':'shadowsocksr'
    }
    
    @staticmethod
    def to_singbox(proxy: Dict[str, Any]) -> Dict[str, Any]:
        """转换为 sing-box 格式，严格按照指定字段顺序"""
        proxy_type = proxy.get('type', '').lower()
        
        singbox_proxy = {
            "tag": proxy.get('name', 'unknown'),
            "type": FormatConverter.TYPE_MAPPING.get(proxy_type, proxy_type),
            "server": proxy.get('server', ''),
            "server_port": proxy.get('port', 0)
        }
        
        converters = {
            'ss': FormatConverter._convert_shadowsocks_to_singbox,
            'vmess': FormatConverter._convert_vmess_to_singbox,
            'vless': FormatConverter._convert_vless_to_singbox,
            'trojan': FormatConverter._convert_trojan_to_singbox,
            'hysteria2': FormatConverter._convert_hysteria2_to_singbox
        }
        
        converter = converters.get(proxy_type)
        if converter:
            converter(proxy, singbox_proxy)
        
        return {k: v for k, v in singbox_proxy.items() if v not in [None, '', 0, {}, []]}
    
    @staticmethod
    def to_surge(proxy: Dict[str, Any]) -> str:
        """转换为 Surge 格式"""
        proxy_type = proxy.get('type', '').lower()
        name = proxy.get('name', 'unknown')
        server = proxy.get('server', '')
        port = proxy.get('port', 0)
        
        converters = {
            'ss': FormatConverter._convert_shadowsocks_to_surge,
            'vmess': FormatConverter._convert_vmess_to_surge,
            'vless': FormatConverter._convert_vless_to_surge,
            'trojan': FormatConverter._convert_trojan_to_surge,
            'hysteria2': FormatConverter._convert_hysteria2_to_surge
        }
        
        converter = converters.get(proxy_type)
        if converter:
            return converter(proxy, name, server, port)
        else:
            return f"# Unsupported proxy type: {proxy_type} - {name}"
    
    # --- Sing-box 转换器 ---
    @staticmethod
    def _convert_shadowsocks_to_singbox(proxy: Dict, singbox_proxy: Dict):
        if proxy.get('cipher'):
            singbox_proxy["method"] = proxy.get('cipher')
        if proxy.get('password'):
            singbox_proxy["password"] = proxy.get('password')
    
    @staticmethod
    def _convert_vmess_to_singbox(proxy: Dict, singbox_proxy: Dict):
        if proxy.get('uuid'):
            singbox_proxy["uuid"] = proxy.get('uuid')
        if proxy.get('cipher'):
            singbox_proxy["security"] = proxy.get('cipher')
        if proxy.get('alterId') is not None:
            singbox_proxy["alter_id"] = proxy.get('alterId', 0)
        FormatConverter._add_transport_and_tls(proxy, singbox_proxy)
    
    @staticmethod
    def _convert_vless_to_singbox(proxy: Dict, singbox_proxy: Dict):
        if proxy.get('uuid'):
            singbox_proxy["uuid"] = proxy.get('uuid')
        if proxy.get('tls'):
            tls_config = {"enabled": True}
            server_name = proxy.get('sni') or proxy.get('servername') or proxy.get('server', '')
            if server_name:
                tls_config["server_name"] = server_name
            tls_config["insecure"] = bool(proxy.get('skip-cert-verify', False))
            if proxy.get('client-fingerprint') or proxy.get('fingerprint'):
                utls_config = {"enabled": True}
                fingerprint = proxy.get('client-fingerprint') or proxy.get('fingerprint')
                if fingerprint:
                    utls_config["fingerprint"] = fingerprint
                tls_config["utls"] = utls_config
            if proxy.get('reality-opts'):
                reality_opts = proxy.get('reality-opts', {})
                reality_config = {"enabled": True}
                if reality_opts.get('public-key'):
                    reality_config["public_key"] = reality_opts.get('public-key')
                if reality_opts.get('short-id'):
                    reality_config["short_id"] = reality_opts.get('short-id')
                tls_config["reality"] = reality_config
            singbox_proxy["tls"] = tls_config
        if proxy.get('network') and proxy.get('network') != 'tcp':
            transport = {"type": proxy.get('network')}
            if proxy.get('network') == 'ws':
                if proxy.get('ws-opts'):
                    ws_opts = proxy.get('ws-opts', {})
                    transport["headers"] = ws_opts.get('headers', {})
                    transport["max_early_data"] = ws_opts.get('max_early_data')
                    if ws_opts.get('path'):
                        transport["path"] = ws_opts.get('path')
                else:
                    transport["headers"] = {}
                    transport["max_early_data"] = None
            singbox_proxy["transport"] = transport
        if proxy.get('flow'):
            singbox_proxy["flow"] = proxy.get('flow')
    
    @staticmethod
    def _convert_trojan_to_singbox(proxy: Dict, singbox_proxy: Dict):
        if proxy.get('password'):
            singbox_proxy["password"] = proxy.get('password')
        tls_config = {"enabled": True}
        server_name = (proxy.get('sni') or proxy.get('servername') or proxy.get('server', ''))
        if server_name:
            tls_config["server_name"] = server_name
        tls_config["insecure"] = bool(proxy.get('skip-cert-verify', False))
        singbox_proxy["tls"] = tls_config
    
    @staticmethod
    def _convert_hysteria2_to_singbox(proxy: Dict, singbox_proxy: Dict):
        if proxy.get('password'):
            singbox_proxy["password"] = proxy.get('password')
        tls_config = {"enabled": True}
        server_name = proxy.get('sni') or proxy.get('server', '')
        if server_name:
            tls_config["server_name"] = server_name
        if proxy.get('skip-cert-verify') is not None:
            tls_config["insecure"] = bool(proxy.get('skip-cert-verify'))
        else:
            tls_config["insecure"] = False
        tls_config["alpn"] = ["h3"]
        singbox_proxy["tls"] = tls_config
    
    @staticmethod
    def _add_transport_and_tls(proxy: Dict, singbox_proxy: Dict):
        if proxy.get('network') and proxy.get('network') != 'tcp':
            transport = {"type": proxy.get('network')}
            if proxy.get('network') == 'ws' and proxy.get('ws-opts'):
                ws_opts = proxy.get('ws-opts', {})
                if ws_opts.get('path'):
                    transport["path"] = ws_opts.get('path')
                if ws_opts.get('headers'):
                    transport["headers"] = ws_opts.get('headers')
            singbox_proxy["transport"] = transport
        if proxy.get('tls'):
            tls_config = {"enabled": True}
            server_name = proxy.get('servername') or proxy.get('sni')
            if server_name:
                tls_config["server_name"] = server_name
            tls_config["insecure"] = bool(proxy.get('skip-cert-verify', False))
            if proxy.get('client-fingerprint') or proxy.get('fingerprint'):
                utls_config = {"enabled": True}
                fingerprint = proxy.get('client-fingerprint') or proxy.get('fingerprint')
                if fingerprint:
                    utls_config["fingerprint"] = fingerprint
                tls_config["utls"] = utls_config
            if proxy.get('reality-opts'):
                reality_opts = proxy.get('reality-opts', {})
                reality_config = {}
                if reality_opts.get('public-key'):
                    reality_config["public_key"] = reality_opts.get('public-key')
                if reality_opts.get('short-id'):
                    reality_config["short_id"] = reality_opts.get('short-id')
                if reality_config:
                    tls_config["reality"] = reality_config
            singbox_proxy["tls"] = tls_config
    
    # --- Surge 转换器 ---
    @staticmethod
    def _convert_shadowsocks_to_surge(proxy: Dict, name: str, server: str, port: int) -> str:
        params = ["ss", server, str(port)]
        if proxy.get('cipher'):
            params.append(f"encrypt-method={proxy.get('cipher')}")
        if proxy.get('password'):
            params.append(f'password="{proxy.get("password")}"')
        if proxy.get('udp'):
            params.append("udp-relay=true")
        return f"{name}={','.join(params)}"
    
    @staticmethod
    def _convert_vmess_to_surge(proxy: Dict, name: str, server: str, port: int) -> str:
        return f"# VMess not fully supported in Surge format - {name}"
    
    @staticmethod
    def _convert_vless_to_surge(proxy: Dict, name: str, server: str, port: int) -> str:
        return f"# VLESS not fully supported in Surge format - {name}"
    
    @staticmethod
    def _convert_trojan_to_surge(proxy: Dict, name: str, server: str, port: int) -> str:
        params = ["trojan", server, str(port)]
        if proxy.get('password'):
            params.append(f'password="{proxy.get("password")}"')
        params.append("tls=true")
        if proxy.get('sni') or proxy.get('servername'):
            sni = proxy.get('sni') or proxy.get('servername')
            params.append(f'sni={sni}')
        if proxy.get('skip-cert-verify'):
            params.append("skip-cert-verify=true")
        if proxy.get('udp'):
            params.append("udp-relay=true")
        return f"{name}={','.join(params)}"
    
    @staticmethod
    def _convert_hysteria2_to_surge(proxy: Dict, name: str, server: str, port: int) -> str:
        params = ["hysteria2", server, str(port)]
        if proxy.get('password'):
            params.append(f'password="{proxy.get("password")}"')
        if proxy.get('sni'):
            params.append(f'sni={proxy.get("sni")}')
        if proxy.get('skip-cert-verify') is not None:
            params.append(f"skip-cert-verify={'true' if proxy.get('skip-cert-verify') else 'false'}")
        if proxy.get('tfo') is not None:
            params.append(f"tfo={'true' if proxy.get('tfo') else 'false'}")
        return f"{name}={','.join(params)}"
        
# --- Service Layer (SOLID - Dependency Inversion) ---
class ProxyService:
    """代理服务层，遵循依赖倒置原则"""
    
    def __init__(self, repository: ProxyRepository):
        self.repository = repository
    
    def get_filtered_proxies(self, country_filter=None, exclude_countries=None, 
                       exclude_keywords=None, include_keywords=None, 
                       is_random=False, num_limit=None) -> List[Dict]:
        """获取过滤后的代理列表（遵循单一职责原则）"""
        proxies = self.repository.get_all_proxies()
        
        # 应用国家过滤器
        if country_filter:
            proxies = [p for p in proxies if p.get('country', '').upper() == country_filter.upper()]
        
        # 应用排除国家过滤器
        if exclude_countries:
            excluded_set = {c.strip().upper() for c in exclude_countries.split(',') if c.strip()}
            proxies = [p for p in proxies if p.get('country', 'UNKNOWN') not in excluded_set]
        
        # 【新增功能】包含关键词过滤器（遵循DRY原则，复用现有的Unicode规范化逻辑）
        if include_keywords:
            normalized_include_kws = [
                unicodedata.normalize('NFKC', k.strip().lower()) 
                for k in include_keywords.split(',') if k.strip()
            ]
            if normalized_include_kws:
                proxies = [
                    p for p in proxies 
                    if any(
                        kw in unicodedata.normalize('NFKC', p.get('name', '').lower()) 
                        for kw in normalized_include_kws
                    )
                ]
        
        # 应用排除关键词过滤器
        if exclude_keywords:
            normalized_exclude_kws = [
                unicodedata.normalize('NFKC', k.strip().lower()) 
                for k in exclude_keywords.split(',') if k.strip()
            ]
            if normalized_exclude_kws:
                proxies = [
                    p for p in proxies 
                    if not any(
                        kw in unicodedata.normalize('NFKC', p.get('name', '').lower()) 
                        for kw in normalized_exclude_kws
                    )
                ]
        
        if is_random:
            random.shuffle(proxies)
        
        if num_limit is not None:
            proxies = proxies[:num_limit]
        
        return proxies
    
    def get_countries(self) -> List[str]:
        """获取国家列表"""
        proxies = self.repository.get_all_proxies()
        countries = sorted(list(set(proxy.get('country', 'UNKNOWN') for proxy in proxies)))
        return countries
        
        
# --- API Logic Layer (重构后，遵循 DRY 原则) ---
class APIController:
    """API 控制器，集中处理请求逻辑"""
    
    def __init__(self, service: ProxyService):
        self.service = service
    
    def list_countries_logic(self):
        """获取国家列表"""
        countries = self.service.get_countries()
        return jsonify({"countries": countries})
    
    def _get_filtered_proxies_from_request(self) -> List[Dict]:
        """从请求中获取过滤参数并返回过滤后的代理列表"""
        country_filter = request.args.get('country')
        exclude_countries_str = request.args.get('exclude_countries', '')
        exclude_keywords_str = request.args.get('exclude_keywords', '')
        include_keywords_str = request.args.get('include_keywords', '')  # 新增参数
        is_random = request.args.get('random', 'false').lower() in ['true', '1']
        
        try:
            num_limit = int(request.args.get('num'))
        except (ValueError, TypeError):
            num_limit = None
        
        return self.service.get_filtered_proxies(
            country_filter=country_filter,
            exclude_countries=exclude_countries_str if exclude_countries_str else None,
            exclude_keywords=exclude_keywords_str if exclude_keywords_str else None,
            include_keywords=include_keywords_str if include_keywords_str else None,  # 新增参数传递
            is_random=is_random,
            num_limit=num_limit
        )

    def get_proxies_logic(self):
        """获取代理列表（YAML 格式）"""
        proxies = self._get_filtered_proxies_from_request()
        proxies_for_output = [{k: v for k, v in p.items() if k != 'country'} for p in proxies]
        response_data = {'proxies': proxies_for_output}
        yaml_output = yaml.dump(response_data, allow_unicode=True, sort_keys=False)
        return Response(yaml_output, mimetype='text/plain; charset=utf-8')

    def get_singbox_config_logic(self):
        """获取 sing-box outbounds 配置（仅返回 outbounds）"""
        proxies = self._get_filtered_proxies_from_request()
        proxies_for_conversion = [{k: v for k, v in p.items() if k != 'country'} for p in proxies]
        outbounds = [FormatConverter.to_singbox(proxy) for proxy in proxies_for_conversion]
        config = {"outbounds": outbounds}
        return Response(
            json.dumps(config, ensure_ascii=False, indent=2),
            mimetype='application/json; charset=utf-8'
        )
    
    def get_surge_config_logic(self):
        """获取 Surge 格式配置"""
        proxies = self._get_filtered_proxies_from_request()
        proxies_for_conversion = [{k: v for k, v in p.items() if k != 'country'} for p in proxies]
        surge_lines = [FormatConverter.to_surge(proxy) for proxy in proxies_for_conversion if FormatConverter.to_surge(proxy)]
        surge_config = "\n".join(surge_lines)
        return Response(surge_config, mimetype='text/plain; charset=utf-8')
    
    def delete_proxy_logic(self, proxy_name: str):
        """删除代理"""
        proxies = self.service.repository.get_all_proxies()
        original_count = len(proxies)
        proxies_to_keep = [p for p in proxies if p.get('name') != proxy_name]
        
        if len(proxies_to_keep) == original_count:
            return jsonify({"error": "Proxy not found", "name": proxy_name}), 404
        
        if self.service.repository.save_proxies(proxies_to_keep):
            return jsonify({"message": "Proxy deleted successfully", "name": proxy_name}), 200
        else:
            return jsonify({"error": "Failed to update proxy file", "name": proxy_name}), 500
    
    def rename_proxy_logic(self):
        """重命名代理"""
        data = request.get_json()
        if not data or 'old_name' not in data or 'new_name' not in data:
            return jsonify({"error": "Request body must be JSON and contain 'old_name' and 'new_name' keys."}), 400

        old_name = data['old_name']
        new_name = data['new_name']

        if not old_name or not new_name:
            return jsonify({"error": "'old_name' and 'new_name' cannot be empty."}), 400

        proxies = self.service.repository.get_all_proxies()
        
        proxy_to_rename = next((p for p in proxies if p.get('name') == old_name), None)
        
        if not proxy_to_rename:
            return jsonify({"error": f"Old name '{old_name}' not found."}), 404

        existing_names = {p.get('name') for p in proxies if p.get('name') != old_name}
        final_name = new_name
        counter = 1
        while final_name in existing_names:
            final_name = f"{new_name}_{counter}"
            counter += 1

        proxy_to_rename['name'] = final_name

        if self.service.repository.save_proxies(proxies):
            return jsonify({
                "message": "Proxy renamed successfully.",
                "old_name": old_name,
                "new_name": final_name
            }), 200
        else:
            return jsonify({"error": "Failed to update proxy file"}), 500
            
            
# --- Dependency Injection Setup (遵循依赖倒置原则) ---
repository = ProxyRepository(Config.PROXIES_FILE_PATH)
service = ProxyService(repository)
api_controller = APIController(service)

# --- Access Control & Routing Layer ---
public_api = Blueprint('public_api', __name__)
private_api = Blueprint('private_api', __name__, url_prefix=Config.SECRET_PATH_PREFIX)
delete_api = Blueprint('delete_api', __name__, url_prefix=f'{Config.SECRET_PATH_PREFIX}/delete')
rename_api = Blueprint('rename_api', __name__, url_prefix=f'{Config.SECRET_PATH_PREFIX}/rename')

def require_valid_ua():
    ua_string = request.headers.get('User-Agent', '').lower()
    if not any(keyword.lower() in ua_string for keyword in Config.ALLOWED_UA_KEYWORDS):
        html_response = """
<!DOCTYPE html>
<html>
<head><title>Access Denied</title></head>
<body><h1>Access Denied</h1><p>Invalid User-Agent</p></body>
</html>
        """
        return Response(html_response, status=403, mimetype='text/html')

@public_api.before_request
def before_request_for_public_api():
    return require_valid_ua()

# --- Route Registration (简化路由定义，遵循 DRY 原则) ---
@public_api.route('/proxies/countries', methods=['GET'])
def public_countries():
    return api_controller.list_countries_logic()

@public_api.route('/proxies', methods=['GET'])
def public_proxies():
    return api_controller.get_proxies_logic()

@public_api.route('/proxies/singbox', methods=['GET'])
def public_singbox():
    return api_controller.get_singbox_config_logic()

@public_api.route('/proxies/surge', methods=['GET'])
def public_surge():
    return api_controller.get_surge_config_logic()

@private_api.route('/proxies/countries', methods=['GET'])
def private_countries():
    return api_controller.list_countries_logic()

@private_api.route('/proxies', methods=['GET'])
def private_proxies():
    return api_controller.get_proxies_logic()

@private_api.route('/proxies/singbox', methods=['GET'])
def private_singbox():
    return api_controller.get_singbox_config_logic()

@private_api.route('/proxies/surge', methods=['GET'])
def private_surge():
    return api_controller.get_surge_config_logic()

@delete_api.route('/<string:proxy_name>', methods=['DELETE'])
def delete_proxy(proxy_name: str):
    return api_controller.delete_proxy_logic(proxy_name)

@rename_api.route('/', methods=['POST'])
def rename_proxy():
    return api_controller.rename_proxy_logic()

# Register all blueprints
app.register_blueprint(public_api)
app.register_blueprint(private_api)
app.register_blueprint(delete_api)
app.register_blueprint(rename_api)

@app.route('/')
def index():
    return "Enhanced API Service is running."

@app.route('/debug/routes')
def list_routes():
    """Debug endpoint to list all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule)
        })
    return jsonify({"routes": routes})

if __name__ == '__main__':
    print("Starting Enhanced Flask server...")
    print(f"Proxy file path: {Config.PROXIES_FILE_PATH}")
    print("API output modes: YAML, sing-box JSON outbounds, Surge format")
    print("Feature: Keyword filtering (include/exclude) is active, robust, and case-insensitive.")
    print("-" * 50)
    print("Available Routes:")
    print(f"  GET  /proxies                             - Get proxies (public)")
    print(f"  GET  {Config.SECRET_PATH_PREFIX}/proxies                    - Get proxies (private)")
    print("\nQuery Parameters Example:")
    print(f"  ?country=US                               - Filter by country code")
    print(f"  ?exclude_countries=HK,SG                 - Exclude multiple countries")
    print(f"  ?include_keywords=高速,优质              - Include nodes with keywords")
    print(f"  ?exclude_keywords=慢速,测试,expire        - Exclude nodes with keywords")
    print(f"  ?random=true                              - Randomize proxy order")
    print(f"  ?num=10                                   - Limit number of results")
    print("-" * 50)
    app.run(port=30374, host='0.0.0.0', debug=False)