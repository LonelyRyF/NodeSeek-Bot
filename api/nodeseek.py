"""
NodeSeek API 客户端 (使用 curl_cffi)
"""
import logging
from typing import List, Dict, Any, Optional

from curl_cffi import requests

from core.config import settings
from core.models import NodeSeekMessage

logger = logging.getLogger(__name__)


class NodeSeekAPI:
    """NodeSeek 论坛 API 客户端"""
    
    BASE_URL = 'https://www.nodeseek.com'
    
    def __init__(self):
        # 创建 session
        self.session = requests.Session()
        
        self._parse_cookies(settings.nodeseek_cookies)
        
        # 设置请求头
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.nodeseek.com/',
        }
        
        # 设置 SOCKS proxy（如果配置了）
        self.proxies = None
        if settings.proxy_host and settings.proxy_port:
            self.proxies = {
                'http': f'socks5://{settings.proxy_host}:{settings.proxy_port}',
                'https': f'socks5://{settings.proxy_host}:{settings.proxy_port}'
            }
            logger.info(f"使用代理: {settings.proxy_host}:{settings.proxy_port}")
        else:
            logger.info("未配置代理，直连")
    
    def _parse_cookies(self, cookie_str: str):
        """解析 cookies"""
        self.cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                self.cookies[key] = value
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送请求"""
        url = f"{self.BASE_URL}{endpoint}"
        response = None
        try:
            # 合并请求参数
            request_kwargs = {
                'headers': self.headers,
                'cookies': self.cookies,
                'impersonate': 'chrome142',
                **kwargs
            }
            
            # 如果配置了代理，则使用代理
            if self.proxies:
                request_kwargs['proxies'] = self.proxies
            
            response = self.session.request(method, url, **request_kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"请求失败 {endpoint}: {e}")
            # 返回详细的 HTTP 响应信息
            if response is not None:
                try:
                    response_text = response.text[:500]
                except:
                    response_text = str(response.content[:500])
                
                return {
                    'success': False,
                    'error': str(e),
                    'status_code': response.status_code,
                    'response_text': response_text,
                    'response_headers': dict(response.headers),
                    'endpoint': endpoint,
                    'method': method
                }
            else:
                return {
                    'success': False,
                    'error': str(e),
                    'endpoint': endpoint,
                    'method': method
                }
    
    def get_messages(self) -> List[Dict]:
        """获取私信列表"""
        logger.info("正在获取 NodeSeek 私信列表...")
        result = self._request('GET', '/api/notification/message/list')
        if result.get('success'):
            messages = result.get('msgArray', [])
            logger.info(f"成功获取 {len(messages)} 条私信")
            return messages
        else:
            logger.error(f"获取私信列表失败: {result.get('error')}")
            return []
    
    def get_message_detail(self, user_id: int) -> List[NodeSeekMessage]:
        """获取与某人的私信记录"""
        result = self._request('GET', f'/api/notification/message/with/{user_id}')
        if result.get('success'):
            msgs = result.get('msgArray', [])
            return [NodeSeekMessage(**m) for m in msgs]
        return []
    
    def mark_viewed(self, message_ids: List[int]) -> bool:
        """标记私信已读"""
        result = self._request(
            'POST',
            '/api/notification/message/markViewed',
            json={'messages': message_ids}
        )
        return result.get('success', False)
    
    def close(self):
        """关闭会话"""
        self.session.close()
