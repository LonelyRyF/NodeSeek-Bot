# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

from typing import Optional, Dict, Any
from curl_cffi import requests


# 统一的请求头配置
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


class HTTPClient:
    """统一的 HTTP 客户端，使用 curl_cffi 进行网络请求"""

    def __init__(self, timeout_seconds: int = 15, proxy_host: str = '', proxy_port: int = 0):
        """
        初始化 HTTP 客户端
        
        Args:
            timeout_seconds: 请求超时时间（秒）
            proxy_host: 代理主机
            proxy_port: 代理端口
        """
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        
        self.proxies = None
        if proxy_host and proxy_port:
            self.proxies = {
                'http': f'socks5://{proxy_host}:{proxy_port}',
                'https': f'socks5://{proxy_host}:{proxy_port}',
            }

    def get(self, url: str, headers: Optional[Dict[str, str]] = None, 
            impersonate: str = 'chrome142', **kwargs) -> requests.Response:
        """
        发送 GET 请求
        
        Args:
            url: 请求 URL
            headers: 自定义请求头（会与默认请求头合并）
            impersonate: curl_cffi 浏览器伪装参数
            **kwargs: 其他请求参数
            
        Returns:
            Response 对象
        """
        merged_headers = DEFAULT_HEADERS.copy()
        if headers:
            merged_headers.update(headers)
        
        request_kwargs = {
            'headers': merged_headers,
            'timeout': self.timeout_seconds,
            'impersonate': impersonate,
            **kwargs
        }
        if self.proxies:
            request_kwargs['proxies'] = self.proxies
        
        return self.session.get(url, **request_kwargs)

    def post(self, url: str, headers: Optional[Dict[str, str]] = None,
             impersonate: str = 'chrome142', **kwargs) -> requests.Response:
        """
        发送 POST 请求
        
        Args:
            url: 请求 URL
            headers: 自定义请求头（会与默认请求头合并）
            impersonate: curl_cffi 浏览器伪装参数
            **kwargs: 其他请求参数
            
        Returns:
            Response 对象
        """
        merged_headers = DEFAULT_HEADERS.copy()
        if headers:
            merged_headers.update(headers)
        
        request_kwargs = {
            'headers': merged_headers,
            'timeout': self.timeout_seconds,
            'impersonate': impersonate,
            **kwargs
        }
        if self.proxies:
            request_kwargs['proxies'] = self.proxies
        
        return self.session.post(url, **request_kwargs)

    def request(self, method: str, url: str, headers: Optional[Dict[str, str]] = None,
                impersonate: str = 'chrome142', **kwargs) -> requests.Response:
        """
        发送通用 HTTP 请求
        
        Args:
            method: HTTP 方法（GET, POST, PUT, DELETE 等）
            url: 请求 URL
            headers: 自定义请求头（会与默认请求头合并）
            impersonate: curl_cffi 浏览器伪装参数
            **kwargs: 其他请求参数
            
        Returns:
            Response 对象
        """
        merged_headers = DEFAULT_HEADERS.copy()
        if headers:
            merged_headers.update(headers)
        
        request_kwargs = {
            'headers': merged_headers,
            'timeout': self.timeout_seconds,
            'impersonate': impersonate,
            **kwargs
        }
        if self.proxies:
            request_kwargs['proxies'] = self.proxies
        
        return self.session.request(method, url, **request_kwargs)

    def close(self):
        """关闭会话"""
        self.session.close()
